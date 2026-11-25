import tkinter as tk
from typing import Callable

from .overlay_layout import PREVIEW_COLOUR, OverlayLayout


class PlacementPreview(tk.Canvas):
    """Draw the primary screen and let the user place the overlay with a drag."""

    def __init__(
        self, parent: tk.Widget, layout: OverlayLayout,
        read_layout: Callable[[], OverlayLayout | None],
        on_place: Callable[[OverlayLayout], None],
    ) -> None:
        super().__init__(parent, width=248, height=126, highlightthickness=0, cursor="hand2")
        self._command: Callable[[OverlayLayout], None] | None = on_place
        self._read_layout: Callable[[], OverlayLayout | None] | None = read_layout
        self._layout = layout
        self._drag_layout: OverlayLayout | None = None
        self._grab_offset: tuple[float, float] | None = None
        self._screen_width = self.winfo_screenwidth()
        self._screen_height = self.winfo_screenheight()
        self.bind("<Configure>", lambda event: self._draw(self._layout))
        self.bind("<ButtonPress-1>", self._start_drag)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", self._drop)

    def show_layout(self, layout: OverlayLayout) -> None:
        """Refresh the miniature to match the applied or edited layout."""
        self._layout = layout
        self._draw(layout)

    def destroy(self) -> None:
        """Release callbacks to the control window on the GUI thread."""
        self._command = None
        self._read_layout = None
        super().destroy()

    def _viewport(self) -> tuple[float, float, float]:
        canvas_width, canvas_height = self.winfo_width(), self.winfo_height()
        scale = min(canvas_width / self._screen_width, canvas_height / self._screen_height)
        return (
            (canvas_width - self._screen_width * scale) / 2,
            (canvas_height - self._screen_height * scale) / 2,
            scale,
        )

    def _draw(self, layout: OverlayLayout) -> None:
        left, top, scale = self._viewport()
        self.delete("all")
        self.create_rectangle(
            left, top, left + self._screen_width * scale, top + self._screen_height * scale,
            fill="#202832", outline="",
        )
        geometry = layout.geometry(self._screen_width, self._screen_height)
        width, height, x, y = geometry.bounds
        bounds = (left + x * scale, top + y * scale,
                  left + (x + width) * scale, top + (y + height) * scale)
        colour = "#%02x%02x%02x" % PREVIEW_COLOUR
        if geometry.polygon:
            self.create_polygon(
                [(left + (x + px) * scale, top + (y + py) * scale) for px, py in geometry.polygon],
                fill=colour, outline=colour,
            )
        else:
            draw_shape = self.create_oval if layout.shape == "circle" else self.create_rectangle
            draw_shape(*bounds, fill=colour, outline=colour)

    def _screen_point(self, event: tk.Event) -> tuple[float, float]:
        left, top, scale = self._viewport()
        return (event.x - left) / scale, (event.y - top) / scale

    def _start_drag(self, event: tk.Event) -> None:
        self._drag_layout = self._read_layout() if self._read_layout is not None else None
        if self._drag_layout is None:
            return
        x, y = self._screen_point(event)
        width, height, left, top = self._drag_layout.bounds(self._screen_width, self._screen_height)
        dx, dy = x - left, y - top
        self._grab_offset = None
        if self._drag_layout.shape != "bar" and 0 <= dx <= width and 0 <= dy <= height:
            self._grab_offset = (dx, dy)
        self._drag(event)

    def _drag(self, event: tk.Event) -> None:
        layout = self._position_at(event)
        if layout is not None:
            self._draw(layout)

    def _drop(self, event: tk.Event) -> None:
        layout = self._position_at(event)
        self._drag_layout = None
        self._draw(self._layout)
        if layout is not None and self._command is not None:
            self._command(layout)

    def _position_at(self, event: tk.Event) -> OverlayLayout | None:
        if self._drag_layout is None:
            return None
        x, y = self._screen_point(event)
        return self._drag_layout.placed_at(
            self._screen_width, self._screen_height, x, y, self._grab_offset
        )
