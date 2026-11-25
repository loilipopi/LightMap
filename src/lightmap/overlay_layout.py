from dataclasses import dataclass

EDGES = ("top", "bottom", "left", "right")


@dataclass(frozen=True)
class OverlayLayout:
    """Describe a full-edge bar or a circle on the primary display."""

    shape: str = "bar"
    edge: str = "top"
    size: int = 48
    x_percent: int = 50
    y_percent: int = 15
    opacity: int = 100

    def __post_init__(self) -> None:
        if self.shape not in ("bar", "circle") or self.edge not in EDGES:
            raise ValueError("Choose a bar edge or a circle.")
        if type(self.size) is not int or self.size < 1:
            raise ValueError("Thickness and radius must be positive whole numbers.")
        if any(type(value) is not int or not 0 <= value <= 100
               for value in (self.x_percent, self.y_percent)):
            raise ValueError("Position must be between 0 and 100 percent.")
        if type(self.opacity) is not int or not 1 <= self.opacity <= 100:
            raise ValueError("Opacity must be between 1 and 100 percent.")

    def bounds(self, screen_width: int, screen_height: int) -> tuple[int, int, int, int]:
        """Return width, height, left and top in screen pixels."""
        if self.shape == "circle":
            diameter = min(2 * self.size, screen_width, screen_height)
            left = round((screen_width - diameter) * self.x_percent / 100)
            top = round((screen_height - diameter) * self.y_percent / 100)
            return diameter, diameter, left, top
        if self.edge in ("top", "bottom"):
            height = min(self.size, screen_height)
            top = screen_height - height if self.edge == "bottom" else 0
            return screen_width, height, 0, top
        width = min(self.size, screen_width)
        left = screen_width - width if self.edge == "right" else 0
        return width, screen_height, left, 0
