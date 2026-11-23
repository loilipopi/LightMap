from math import isfinite
from numbers import Integral
from os import PathLike
from threading import Lock, RLock

from .app_model import AppState, CaptureStatus
from .audio_capture import AudioCapture
from .audio_analyser import FrequencyAnalyser
from .colour_mapper import ColourMapImage, ColourMapper
from .control_view import ControlView
from .overlay_view import OverlayView


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
            sample_rate = self._map_settings.get("sample_rate")
            if "sample_rate" in self._map_settings and (
                isinstance(sample_rate, bool)
                or not isinstance(sample_rate, (int, float))
                or not isfinite(sample_rate)
                or sample_rate <= 0
            ):
                raise ValueError("colour map sample_rate must be finite and positive")
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
            overlay.set_colour(self._model.output_colour)
            if self._model.overlay_enabled:
                overlay.show()
            else:
                overlay.hide()

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
            for spectrum in spectra:
                colour = mapper.map_colour(spectrum)
            self._model.output_colour = colour
            if self._overlay is not None:
                self._overlay.set_colour(self._model.output_colour)

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
            self._report_error(message)

    def set_overlay_enabled(self, enabled: bool) -> None:
        """Show the latest output colour when enabled, or hide the overlay."""
        with self._state:
            if self._closed:
                return
            self._model.overlay_enabled = enabled
            if self._overlay is not None:
                if enabled:
                    self._overlay.set_colour(self._model.output_colour)
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
