from dataclasses import dataclass, replace
from math import ceil, cos, radians, sin

EDGES = ("top", "bottom", "left", "right")
PREVIEW_COLOUR = (114, 204, 228)
POLYGONS = {
    "rectangle": ((-.5, -.5), (.5, -.5), (.5, .5), (-.5, .5)),
    "triangle": ((0, -.5), (.5, .5), (-.5, .5)),
    "diamond": ((0, -.5), (.5, 0), (0, .5), (-.5, 0)),
    "hexagon": ((-.25, -.5), (.25, -.5), (.5, 0),
                (.25, .5), (-.25, .5), (-.5, 0)),
}
SHAPES = ("bar", "circle", *POLYGONS)


@dataclass(frozen=True)
class OverlayGeometry:
    """The screen bounds and any polygon outline in window-local coordinates."""

    bounds: tuple[int, int, int, int]
    polygon: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class OverlayLayout:
    """Describe an edge bar or a floating shape on the primary display."""

    shape: str = "bar"
    edge: str = "top"
    size: int = 48
    x_percent: int = 50
    y_percent: int = 15
    opacity: int = 100
    width: int = 160
    height: int = 80
    rotation: int = 0

    def __post_init__(self) -> None:
        if self.shape not in SHAPES or self.edge not in EDGES:
            raise ValueError("Choose a supported shape and bar edge.")
        if type(self.size) is not int or self.size < 1:
            raise ValueError("Thickness and radius must be positive whole numbers.")
        if any(type(value) is not int or not 1 <= value <= 4096
               for value in (self.width, self.height)):
            raise ValueError("Shape width and height must be whole pixels from 1 to 4096.")
        if type(self.rotation) is not int:
            raise ValueError("Rotation must be entered in whole degrees.")
        if any(type(value) is not int or not 0 <= value <= 100
               for value in (self.x_percent, self.y_percent)):
            raise ValueError("Position must be between 0 and 100 percent.")
        if type(self.opacity) is not int or not 1 <= self.opacity <= 100:
            raise ValueError("Opacity must be between 1 and 100 percent.")

    def bounds(self, screen_width: int, screen_height: int) -> tuple[int, int, int, int]:
        """Return width, height, left and top in screen pixels."""
        return self.geometry(screen_width, screen_height).bounds

    def geometry(self, screen_width: int, screen_height: int) -> OverlayGeometry:
        """Fit the rotated outline within the display for the preview and overlay."""
        if self.shape == "bar":
            if self.edge in ("top", "bottom"):
                height = min(self.size, screen_height)
                top = screen_height - height if self.edge == "bottom" else 0
                return OverlayGeometry((screen_width, height, 0, top))
            width = min(self.size, screen_width)
            left = screen_width - width if self.edge == "right" else 0
            return OverlayGeometry((width, screen_height, left, 0))

        outline = ()
        if self.shape == "circle":
            width = height = min(2 * self.size, screen_width, screen_height)
        else:
            angle = radians(self.rotation % 360)
            c, s = cos(angle), sin(angle)
            points = [
                (x * self.width * c - y * self.height * s, x * self.width * s + y * self.height * c)
                for x, y in POLYGONS[self.shape]
            ]
            xs, ys = zip(*points)
            min_x, min_y = min(xs), min(ys)
            span_x, span_y = max(xs) - min_x, max(ys) - min_y
            scale = min(1, screen_width / span_x, screen_height / span_y)
            # Right angles can produce fractional round-off above an integer.
            width = max(1, ceil(span_x * scale - 1e-9))
            height = max(1, ceil(span_y * scale - 1e-9))
            outline = tuple(((x - min_x) * scale, (y - min_y) * scale) for x, y in points)
        left = round((screen_width - width) * self.x_percent / 100)
        top = round((screen_height - height) * self.y_percent / 100)
        return OverlayGeometry((width, height, left, top), outline)

    def placed_at(
        self, width: int, height: int, x: float, y: float,
        grab_offset: tuple[float, float] | None = None,
    ) -> "OverlayLayout":
        """Place a floating shape or snap a bar to the nearest edge."""
        if self.shape == "bar":
            distances = (abs(y), abs(height - y), abs(x), abs(width - x))
            return replace(self, edge=min(zip(distances, EDGES), key=lambda item: item[0])[1])

        shape_width, shape_height, _, _ = self.bounds(width, height)
        offset_x, offset_y = grab_offset or (shape_width / 2, shape_height / 2)
        room_x, room_y = width - shape_width, height - shape_height
        px = round(100 * min(max(x - offset_x, 0), room_x) / room_x) if room_x else self.x_percent
        py = round(100 * min(max(y - offset_y, 0), room_y) / room_y) if room_y else self.y_percent
        return replace(self, x_percent=px, y_percent=py)
