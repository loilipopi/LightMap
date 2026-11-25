import argparse
import sys
from pathlib import Path
from tkinter import TclError

from .app_controller import AppController
from .app_model import AppModel
from .audio_analyser import FrequencyAnalyser
from .audio_capture import AudioCapture
from .control_view import ControlView
from .overlay_view import OverlayView

BUNDLED_MAPS = Path(__file__).resolve().parents[1] / "map"
PALETTES = {name.title(): BUNDLED_MAPS / f"{name}.png" for name in ("spectrum", "ember", "ocean")}


def main(argv: list[str] | None = None) -> int:
    """Run the desktop app with a bundled map name or a custom image path."""
    parser = argparse.ArgumentParser(description="Turn Windows playback audio into a colour overlay.")
    parser.add_argument(
        "--map",
        default="spectrum",
        metavar="NAME_OR_PATH",
        help="spectrum (default), ember, ocean, or a custom image file",
    )
    args = parser.parse_args(argv)
    path = Path(args.map)
    if args.map in ("spectrum", "ember", "ocean") and not path.is_file():
        path = BUNDLED_MAPS / f"{args.map}.png"

    try:
        controller = AppController(
            AppModel(), AudioCapture(), FrequencyAnalyser(), colour_map_path=path
        )
        controller.set_smoothing_enabled(True)
        controls = ControlView(
            controller.start, controller.stop, controller.set_overlay_enabled, controller.close,
            palettes=PALETTES,
            current_palette=path,
            on_palette_change=controller.set_colour_map,
            on_smoothing_toggle=controller.set_smoothing_enabled,
            on_layout_change=controller.set_overlay_layout,
        )
        try:
            overlay = OverlayView()
            try:
                controller.set_views(controls, overlay)
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
