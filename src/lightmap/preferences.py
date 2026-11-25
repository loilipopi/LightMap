import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile

from .app_model import RGB
from .overlay_layout import OverlayLayout

MIN_FLOOR_DB = -100
MAX_FLOOR_DB = -20
MAX_EMPHASIS = 300
MAX_FADE_MS = 5000


@dataclass(frozen=True)
class AudioTuning:
    """Set the quiet threshold, background and relative weight of each band."""

    floor_db: int = -60
    quiet_colour: RGB = (0, 0, 0)
    low: int = 100
    mid: int = 100
    high: int = 100

    def __post_init__(self) -> None:
        if type(self.floor_db) is not int or not MIN_FLOOR_DB <= self.floor_db <= MAX_FLOOR_DB:
            raise ValueError(f"The noise floor must be between {MIN_FLOOR_DB} and {MAX_FLOOR_DB} dB.")
        if any(type(gain) is not int or not 0 <= gain <= MAX_EMPHASIS
               for gain in (self.low, self.mid, self.high)):
            raise ValueError(f"Each band must be between 0 and {MAX_EMPHASIS}%.")
        colour = self.quiet_colour
        if not isinstance(colour, tuple) or len(colour) != 3 or any(
            type(channel) is not int or not 0 <= channel <= 255 for channel in colour
        ):
            raise ValueError("The quiet colour must contain three RGB channels from 0 to 255.")

    def weight(self, frequency: float) -> float:
        """Return the power multiplier for a frequency in Hz."""
        if frequency < 250:
            return self.low / 100
        if frequency < 4000:
            return self.mid / 100
        return self.high / 100


@dataclass(frozen=True)
class SmoothingTimes:
    """Time constants for rising and falling audio, in milliseconds."""

    fade_in_ms: int = 35
    fade_out_ms: int = 35

    def __post_init__(self) -> None:
        if any(type(value) is not int or not 0 <= value <= MAX_FADE_MS
               for value in (self.fade_in_ms, self.fade_out_ms)):
            raise ValueError(f"Fade times must be whole milliseconds from 0 to {MAX_FADE_MS}.")


@dataclass(frozen=True)
class AppPreferences:
    palette: str = "spectrum"
    smoothing: bool = True
    overlay_enabled: bool = False
    layout: OverlayLayout = field(default_factory=OverlayLayout)
    audio: AudioTuning = field(default_factory=AudioTuning)
    smoothing_times: SmoothingTimes = field(default_factory=SmoothingTimes)


def preferences_path() -> Path:
    """Locate the per-user settings file outside the checkout."""
    local = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CONFIG_HOME")
    return (Path(local) if local else Path.home() / ".config") / "LightMap" / "settings.json"


def load_preferences(path: Path) -> AppPreferences:
    """Read saved preferences, using defaults for unusable entries."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return AppPreferences()
    if not isinstance(data, dict):
        return AppPreferences()

    try:
        layout = OverlayLayout(**data.get("layout", {}))
    except (TypeError, ValueError):
        layout = OverlayLayout()
    try:
        audio = dict(data.get("audio", {}))
        if "quiet_colour" in audio:
            audio["quiet_colour"] = tuple(audio["quiet_colour"])
        tuning = AudioTuning(**audio)
    except (TypeError, ValueError):
        tuning = AudioTuning()
    try:
        times = SmoothingTimes(**data.get("smoothing_times", {}))
    except (TypeError, ValueError):
        times = SmoothingTimes()
    palette = data.get("palette")
    smoothing = data.get("smoothing")
    enabled = data.get("overlay_enabled")
    return AppPreferences(
        palette=palette if isinstance(palette, str) and palette else "spectrum",
        smoothing=smoothing if isinstance(smoothing, bool) else True,
        overlay_enabled=enabled if isinstance(enabled, bool) else False,
        layout=layout,
        audio=tuning,
        smoothing_times=times,
    )


def save_preferences(path: Path, preferences: AppPreferences) -> None:
    """Replace the settings file atomically after writing its new contents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # The temporary file must live beside the destination for atomic replacement.
    temporary = None
    try:
        with NamedTemporaryFile(dir=path.parent, suffix=".tmp", mode="w",
                                encoding="utf-8", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(asdict(preferences), handle, indent=2)
            handle.write("\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
