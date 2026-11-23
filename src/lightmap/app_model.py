from numbers import Integral
from typing import Literal, Protocol

CaptureStatus = Literal["stopped", "active", "error"]
RGB = tuple[int, int, int]


class AppState(Protocol):
    """Mutable application state needed by the controller."""

    capture_status: CaptureStatus
    settings: dict[str, float]
    output_colour: RGB
    overlay_enabled: bool


class AppModel:
    """Store capture status, processing settings, and overlay state."""

    def __init__(self) -> None:
        """Start stopped with empty settings and a hidden, black overlay."""
        self._capture_status: CaptureStatus = "stopped"
        self.settings: dict[str, float] = {}
        self._output_colour: RGB = (0, 0, 0)
        self._overlay_enabled = False

    @property
    def capture_status(self) -> CaptureStatus:
        """Return the current capture status."""
        return self._capture_status

    @capture_status.setter
    def capture_status(self, status: CaptureStatus) -> None:
        if not isinstance(status, str) or status not in ("stopped", "active", "error"):
            raise ValueError("capture status must be stopped, active, or error")
        self._capture_status = status

    @property
    def output_colour(self) -> RGB:
        """Return the latest RGB output colour."""
        return self._output_colour

    @output_colour.setter
    def output_colour(self, colour: RGB) -> None:
        if not isinstance(colour, tuple) or len(colour) != 3 or any(
            isinstance(channel, bool)
            or not isinstance(channel, Integral)
            or not 0 <= channel <= 255
            for channel in colour
        ):
            raise ValueError("output colour must be an RGB tuple with channels from 0 to 255")
        red, green, blue = colour
        self._output_colour = (int(red), int(green), int(blue))

    @property
    def overlay_enabled(self) -> bool:
        """Return whether the overlay is enabled."""
        return self._overlay_enabled

    @overlay_enabled.setter
    def overlay_enabled(self, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            raise TypeError("overlay enabled must be a boolean")
        self._overlay_enabled = enabled
