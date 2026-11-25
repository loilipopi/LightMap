import argparse
from pathlib import Path
from tkinter import TclError

from .app_controller import AppController
from .app_model import AppModel
from .audio_analyser import FrequencyAnalyser
from .audio_capture import AudioCapture
from .control_view import ControlView
from .overlay_view import OverlayView

BUNDLED_MAPS = Path(__file__).resolve().parents[1] / "map"


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
        controls = ControlView(
            controller.start, controller.stop, controller.set_overlay_enabled, controller.close
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
        parser.exit(1, f"LightMap: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
