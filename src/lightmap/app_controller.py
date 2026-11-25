from math import expm1, isfinite, log10
from numbers import Integral
from os import PathLike
from threading import Lock, RLock
from time import monotonic

from .app_model import AppState, CaptureStatus, RGB
from .audio_capture import CHUNK_SIZE, AudioCapture
from .audio_analyser import FrequencyAnalyser
from .colour_mapper import DEFAULT_MAX_MAGNITUDE, ColourMapImage, ColourMapper
from .control_view import ControlView
from .overlay_layout import PREVIEW_COLOUR, OverlayLayout
from .overlay_view import OverlayView
from .preferences import AudioTuning, SmoothingTimes

IDLE_SECONDS = 0.25


class AppController:
    """Coordinate capture, analysis, colour mapping, and the views."""

    def __init__(
        self,
        model: AppState,
        capture: AudioCapture,
        analyser: FrequencyAnalyser,
        mapper: ColourMapper | None = None,
        *,
        colour_map_path: str | PathLike[str] | None = None,
        colour_map_settings: dict[str, float] | None = None,
    ) -> None:
        """Use a configured mapper, or load an image and configure one.

        An injected mapper must already match the capture sample rate.
        Image-backed maps use the reported rate. A configured initial rate
        prepares the mapper immediately. Missing or unreadable images raise
        FileNotFoundError or ValueError, respectively.
        """
        if (mapper is None) == (colour_map_path is None):
            raise ValueError("provide either a configured mapper or a colour map path")
        if mapper is not None and colour_map_settings is not None:
            raise ValueError("configure an injected mapper before passing it in")

        self._model = model
        self._capture = capture
        self._analyser = analyser
        self._mapper = mapper
        self._colour_map: ColourMapImage | None = None
        self._map_settings: dict[str, float] = {}
        self._mapper_sample_rate: float | None = None
        self._latest_spectrum: list[tuple[float, float]] | None = None
        self._latest_colour = model.output_colour
        self._tuning: AudioTuning | None = None
        self._last_frame_time: float | None = None
        self._smoothing_enabled = False
        self._smoothing_times = SmoothingTimes()
        self._smoothed: tuple[float, float, float] | None = None
        self._latest_signal = 0.0
        self._fading_out = False
        self._quiet_fade_at: float | None = None
        self._overlay_layout: OverlayLayout | None = None
        self._preview_enabled = False
        self._controls: ControlView | None = None
        self._overlay: OverlayView | None = None
        self._closed = False
        self._session: object | None = None
        self._starting = False
        self._capture_needs_stop = False

        # Capture may invoke callbacks during start or wait for them during
        # stop. Serialize lifecycle commands without locking callbacks out.
        self._commands = Lock()
        self._state = RLock()

        if colour_map_path is not None:
            self._map_settings = dict(
                model.settings if colour_map_settings is None else colour_map_settings
            )
            # Reject bad settings now rather than inside a capture callback.
            # min_frequency < fs / 2 is checked once the sample rate is known.
            for key, sign in (
                ("sample_rate", "positive"),
                ("max_magnitude", "positive"),
                ("min_frequency", "positive"),
                ("floor_db", "negative"),
            ):
                value = self._map_settings.get(key)
                if key in self._map_settings and (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not isfinite(value)
                    or (value <= 0 if sign == "positive" else value >= 0)
                ):
                    raise ValueError(f"colour map {key} must be finite and {sign}")
            sample_rate = self._map_settings.get("sample_rate")
            self._colour_map = self._load_colour_map(colour_map_path)
            if sample_rate is not None:
                self._mapper_for_rate(sample_rate)
            model.settings.update(self._map_settings)

    @staticmethod
    def _load_colour_map(colour_map_path: str | PathLike[str]) -> ColourMapImage:
        """Decode the image into rows of RGB pixels."""
        from PIL import Image

        try:
            with Image.open(colour_map_path) as image, image.convert("RGB") as rgb:
                pixels = rgb.load()
                return [[pixels[x, y] for x in range(rgb.width)] for y in range(rgb.height)]
        except FileNotFoundError:
            raise
        except (OSError, Image.DecompressionBombError) as exc:
            raise ValueError(f"cannot read colour map image: {colour_map_path}") from exc

    def _mapper_for_rate(self, sample_rate: float) -> ColourMapper:
        if self._colour_map is not None and self._mapper_sample_rate != sample_rate:
            settings = {**self._map_settings, "sample_rate": sample_rate}
            self._mapper = ColourMapper(self._colour_map, settings)
            self._mapper_sample_rate = sample_rate
        assert self._mapper is not None
        return self._mapper

    def set_views(self, controls: ControlView, overlay: OverlayView) -> None:
        """Attach the views and synchronize them with the current state."""
        with self._state:
            if self._closed:
                raise RuntimeError("the application is closed")
            self._controls = controls
            self._overlay = overlay
            controls.set_status(self._model.capture_status)
            if self._overlay_layout is not None:
                overlay.set_layout(self._overlay_layout)
            self._sync_overlay()

    def start(self) -> None:
        """Reset the analyser and open one capture session if none is open."""
        with self._commands:
            with self._state:
                if self._closed or self._session is not None:
                    return
            if self._capture_needs_stop and not self._stop_capture():
                return

            with self._state:
                self._analyser.reset()
                self._last_frame_time = None
                self._latest_spectrum = None
                self._quiet_fade_at = None
                self._latest_signal = 0.0
                self._fading_out = False
                self._smoothed = self._model.output_colour if self._smoothing_enabled else None
                session = self._session = object()
                self._starting = True
                self._capture_needs_stop = True

            def receive_samples(samples: list[float], sample_rate: int) -> None:
                with self._state:
                    if self._session is session:
                        self.on_samples(samples, sample_rate)

            def receive_error(message: str) -> None:
                with self._state:
                    if self._session is session:
                        self.on_error(message)

            try:
                self._capture.start(receive_samples, receive_error)
            except Exception as exc:
                receive_error(str(exc) or type(exc).__name__)

            with self._state:
                self._starting = False
                if self._session is session:
                    self._set_status("active")
                    return

            # A startup failure can leave a partially opened device.
            self._stop_capture()

    def stop(self) -> None:
        """Stop capture, discard buffered samples, and update the status."""
        with self._commands:
            with self._state:
                if self._closed:
                    return
                self._session = None
                self._analyser.reset()
                self._reset_input()
            if self._capture_needs_stop and not self._stop_capture():
                return
            with self._state:
                self._set_status("stopped")

    def on_samples(self, samples: list[float], sample_rate: int) -> None:
        """Publish the latest complete window's colour, rejecting invalid rates."""
        with self._state:
            if self._session is None:
                return
            if (
                isinstance(sample_rate, bool)
                or not isinstance(sample_rate, Integral)
                or sample_rate <= 0
            ):
                raise ValueError("capture sample_rate must be a positive integer")
            spectra = self._analyser.analyse(samples, sample_rate)
            self._model.settings["sample_rate"] = sample_rate
            if not spectra:
                return
            mapper = self._mapper_for_rate(sample_rate)
            self._quiet_fade_at = None
            for spectrum in spectra:
                colour = self._map_spectrum(mapper, spectrum)
                peak = max((magnitude for _, magnitude in spectrum), default=0.0)
                signal = 0.0 if self._tuning is not None and colour == self._tuning.quiet_colour else peak
                if signal != self._latest_signal:
                    self._fading_out = signal < self._latest_signal
                elif colour != self._latest_colour:
                    self._fading_out = False
                self._latest_signal, self._latest_colour = signal, colour
                if self._smoothing_enabled:
                    milliseconds = (
                        self._smoothing_times.fade_out_ms if self._fading_out
                        else self._smoothing_times.fade_in_ms
                    )
                    colour = self._smooth(colour, milliseconds, CHUNK_SIZE / sample_rate)
            self._latest_spectrum = spectra[-1]
            if self._tuning is not None:
                self._last_frame_time = monotonic()
                if self._controls is not None:
                    reference = self._map_settings.get("max_magnitude", DEFAULT_MAX_MAGNITUDE)
                    level = 20 * (log10(peak) - log10(reference)) if peak > 0 else None
                    self._controls.set_input_level(level)
            self._publish_colour(colour)

    def set_colour_map(self, path: str | PathLike[str]) -> None:
        """Load a palette and apply it to the latest spectrum, if available."""
        pixels = self._load_colour_map(path)
        with self._state:
            if self._closed:
                return
            sample_rate = self._model.settings.get("sample_rate")
            if sample_rate is None:
                mapper = None
            else:
                mapper = ColourMapper(pixels, {**self._map_settings, "sample_rate": sample_rate})
            spectrum = self._latest_spectrum
            colour = self._map_spectrum(mapper, spectrum)
            self._colour_map = pixels
            self._mapper = mapper
            self._mapper_sample_rate = sample_rate
            self._show_new_target(colour)

    def set_audio_tuning(self, tuning: AudioTuning) -> None:
        """Apply sensitivity, quiet colour and band weights to the current input."""
        with self._state:
            if not self._closed:
                self._tuning = tuning
                self._show_new_target(self._map_spectrum(self._mapper, self._latest_spectrum))

    def refresh_idle(self) -> None:
        """Clear stale input and advance any quiet fade between audio frames."""
        with self._state:
            if self._last_frame_time is None and self._quiet_fade_at is None:
                return
            now = monotonic()
            if self._last_frame_time is not None and now - self._last_frame_time >= IDLE_SECONDS:
                self._reset_input(now)
            if self._quiet_fade_at is not None:
                colour = self._smooth(
                    self._latest_colour, self._smoothing_times.fade_out_ms, now - self._quiet_fade_at
                )
                self._quiet_fade_at = now
                if colour == self._latest_colour:
                    self._show_new_target(colour)
                else:
                    self._publish_colour(colour)

    def _map_spectrum(
        self, mapper: ColourMapper | None, spectrum: list[tuple[float, float]] | None
    ) -> RGB:
        if mapper is None or not spectrum:
            return (0, 0, 0) if self._tuning is None else self._tuning.quiet_colour
        if self._tuning is None:
            return mapper.map_colour(spectrum)
        return mapper.map_colour(spectrum, tuning=self._tuning)

    def _show_new_target(self, colour: RGB) -> None:
        self._latest_colour = colour
        self._quiet_fade_at = None
        self._smoothed = colour if self._smoothing_enabled else None
        self._publish_colour(colour)

    def _reset_input(self, now: float | None = None) -> None:
        if self._tuning is not None:
            self._last_frame_time = None
            self._latest_spectrum = None
            self._latest_signal = 0.0
            self._fading_out = True
            if self._controls is not None:
                self._controls.set_input_level(None)
            quiet = self._tuning.quiet_colour
            if (self._smoothing_enabled and self._smoothing_times.fade_out_ms
                    and self._model.output_colour != quiet):
                self._latest_colour = quiet
                self._quiet_fade_at = monotonic() if now is None else now
            else:
                self._show_new_target(quiet)

    def set_smoothing_enabled(self, enabled: bool) -> None:
        """Toggle the short visual transition without changing FFT or mapping."""
        with self._state:
            if self._closed or enabled == self._smoothing_enabled:
                return
            self._smoothing_enabled = enabled
            self._smoothed = self._model.output_colour if enabled else None
            if not enabled:
                self._show_new_target(self._latest_colour)

    def set_smoothing_times(self, times: SmoothingTimes) -> None:
        """Set separate time constants for louder and quieter audio."""
        with self._state:
            if self._closed:
                return
            self._smoothing_times = times
            if self._quiet_fade_at is not None and not times.fade_out_ms:
                self._show_new_target(self._latest_colour)

    def set_overlay_layout(self, layout: OverlayLayout) -> None:
        """Apply geometry and opacity without changing the overlay visibility."""
        with self._state:
            if self._closed:
                return
            if self._overlay is not None:
                self._overlay.set_layout(layout)
            self._overlay_layout = layout

    def _smooth(self, colour: RGB, milliseconds: int, seconds: float) -> RGB:
        if not milliseconds or self._smoothed is None:
            self._smoothed = colour
            return colour
        weight = -expm1(-seconds * 1000 / milliseconds)
        red, green, blue = (
            old + (new - old) * weight for old, new in zip(self._smoothed, colour)
        )
        self._smoothed = (red, green, blue)
        return round(red), round(green), round(blue)

    def _publish_colour(self, colour: RGB) -> None:
        self._model.output_colour = colour
        if self._overlay is not None and not self._preview_enabled:
            self._overlay.set_colour(colour)

    def on_error(self, message: str) -> None:
        """Discard the failed session reported by AudioCapture and show its error."""
        with self._state:
            if self._session is None:
                return
            self._session = None
            # AudioCapture releases a failed session before reporting it.
            # During startup, start() also cleans up any partially opened device.
            if not self._starting:
                self._capture_needs_stop = False
            self._analyser.reset()
            self._reset_input()
            self._report_error(message)

    def set_overlay_enabled(self, enabled: bool) -> None:
        """Show the latest output colour when enabled, or hide the overlay."""
        with self._state:
            if self._closed:
                return
            self._model.overlay_enabled = enabled
            self._sync_overlay()

    def set_overlay_preview(self, enabled: bool) -> None:
        """Temporarily show a sample colour independent of capture and visibility."""
        with self._state:
            if self._closed:
                return
            self._preview_enabled = enabled
            self._sync_overlay()

    def _sync_overlay(self) -> None:
        if self._overlay is None:
            return
        colour = PREVIEW_COLOUR if self._preview_enabled else self._model.output_colour
        self._overlay.set_colour(colour)
        if self._preview_enabled or self._model.overlay_enabled:
            self._overlay.show()
        else:
            self._overlay.hide()

    def close(self) -> None:
        """Close both views and release capture, retrying a failed release on reentry."""
        with self._commands:
            with self._state:
                if self._closed and not self._capture_needs_stop:
                    return
                if not self._closed:
                    self._session = None
                    self._model.overlay_enabled = False
                    self._analyser.reset()
                self._closed = True
                controls, overlay = self._controls, self._overlay

            try:
                if self._stop_capture():
                    with self._state:
                        self._set_status("stopped")
            finally:
                with self._state:
                    self._controls = None
                    self._overlay = None
                try:
                    if overlay is not None:
                        overlay.close()
                finally:
                    if controls is not None:
                        controls.close()

    def _stop_capture(self) -> bool:
        """Release the device without holding the callback state lock."""
        try:
            self._capture.stop()
        except Exception as exc:
            with self._state:
                self._capture_needs_stop = True
                self._report_error(str(exc) or type(exc).__name__)
            return False
        with self._state:
            self._capture_needs_stop = False
        return True

    def _set_status(self, status: CaptureStatus) -> None:
        self._model.capture_status = status
        if self._controls is not None:
            self._controls.set_status(status)

    def _report_error(self, message: str) -> None:
        self._set_status("error")
        if self._controls is not None:
            self._controls.show_error(message or "Audio capture failed")
