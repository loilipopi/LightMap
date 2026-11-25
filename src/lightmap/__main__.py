import argparse
import sys
from dataclasses import replace
from pathlib import Path
from tkinter import TclError

from .app_controller import AppController
from .app_model import AppModel
from .audio_analyser import FrequencyAnalyser
from .audio_capture import AudioCapture
from .control_view import ControlView
from .overlay_view import OverlayView
from .preferences import load_preferences, preferences_path, save_preferences

BUNDLED_MAPS = Path(__file__).resolve().parents[1] / "map"
PALETTES = {
    name.title(): BUNDLED_MAPS / f"{name}.png"
    for name in ("spectrum", "ember", "ocean", "rainbow", "octaves")
}
LIVE_WINDOW_SIZE = 2048
LIVE_HOP_SIZE = 256


def _palette_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_file() else PALETTES.get(value.title(), path)


def main(argv: list[str] | None = None) -> int:
    """Run the desktop app with a bundled map name or a custom image path."""
    parser = argparse.ArgumentParser(description="Turn Windows playback audio into a colour overlay.")
    parser.add_argument(
        "--map",
        metavar="NAME_OR_PATH",
        help="override the saved palette with spectrum, ember, ocean, rainbow, octaves, or an image file",
    )
    args = parser.parse_args(argv)
    settings_file = preferences_path()
    prefs = load_preferences(settings_file)
    saved_prefs = prefs
    try:
        path = _palette_path(args.map if args.map is not None else prefs.palette)
        notice = ""
        try:
            controller = AppController(
                AppModel(),
                AudioCapture(chunk_size=LIVE_HOP_SIZE),
                FrequencyAnalyser(
                    window_size=LIVE_WINDOW_SIZE, hop_size=LIVE_HOP_SIZE, window="low_latency"
                ),
                colour_map_path=path,
            )
        except (OSError, ValueError):
            if args.map is not None or path == PALETTES["Spectrum"]:
                raise
            path = PALETTES["Spectrum"]
            controller = AppController(
                AppModel(),
                AudioCapture(chunk_size=LIVE_HOP_SIZE),
                FrequencyAnalyser(
                    window_size=LIVE_WINDOW_SIZE, hop_size=LIVE_HOP_SIZE, window="low_latency"
                ),
                colour_map_path=path,
            )
            notice = "The saved colour map could not be opened. Spectrum is active."
        controller.set_smoothing_enabled(prefs.smoothing)
        controller.set_smoothing_times(prefs.smoothing_times)
        controller.set_overlay_enabled(prefs.overlay_enabled)
        controller.set_overlay_layout(prefs.layout)
        controller.set_audio_tuning(prefs.audio)

        def remember(**changes) -> None:
            nonlocal prefs, saved_prefs
            prefs = replace(prefs, **changes)
            if prefs != saved_prefs:
                try:
                    save_preferences(settings_file, prefs)
                except OSError as exc:
                    controls.show_settings_notice(f"Could not save preferences: {exc}")
                    return
                saved_prefs = prefs

        def select_palette(selected: Path) -> None:
            controller.set_colour_map(selected)
            palette = next((name.lower() for name, file in PALETTES.items() if file == selected), None)
            remember(palette=palette or str(selected.resolve()))

        def save_change(field, apply):
            def change(value):
                apply(value)
                remember(**{field: value})
            return change

        controls = ControlView(
            controller.start, controller.stop,
            save_change("overlay_enabled", controller.set_overlay_enabled), controller.close,
            palettes=PALETTES, current_palette=path, on_palette_change=select_palette,
            on_smoothing_toggle=save_change("smoothing", controller.set_smoothing_enabled),
            on_smoothing_times_change=save_change("smoothing_times", controller.set_smoothing_times),
            on_layout_change=save_change("layout", controller.set_overlay_layout),
            preferences=prefs,
            on_preview_toggle=controller.set_overlay_preview,
            on_audio_change=save_change("audio", controller.set_audio_tuning),
            on_idle_check=controller.refresh_idle,
        )
        try:
            overlay = OverlayView()
            try:
                controller.set_views(controls, overlay)
                if notice:
                    controls.show_settings_notice(notice)
                controls.show()
                controls.run()
            finally:
                controller.close()
                overlay.close()
        finally:
            controls.close()
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, TclError, ValueError) as exc:
        if sys.platform == "win32" and Path(sys.executable).name.lower() == "pythonw.exe":
            from ctypes import windll

            windll.user32.MessageBoxW(None, str(exc), "LightMap could not start", 0x10)
            return 1
        parser.exit(1, f"LightMap: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
