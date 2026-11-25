import tkinter as tk
from pathlib import Path
from queue import Empty, SimpleQueue
from tkinter import filedialog, ttk
from typing import Callable

from .app_model import CaptureStatus
from .overlay_layout import EDGES, OverlayLayout

POLL_MS = 20


class ControlView:
    """Show playback controls on the GUI thread and accept worker updates."""

    def __init__(
        self,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_overlay_toggle: Callable[[bool], None],
        on_close: Callable[[], None],
        *,
        palettes: dict[str, Path] | None = None,
        current_palette: Path | None = None,
        on_palette_change: Callable[[Path], None] | None = None,
        on_smoothing_toggle: Callable[[bool], None] | None = None,
        on_layout_change: Callable[[OverlayLayout], None] | None = None,
    ) -> None:
        """Create a hidden window with the controller's callbacks attached."""
        self._updates: SimpleQueue[tuple[str, str]] = SimpleQueue()
        self._root = tk.Tk()
        self._root.withdraw()
        self._root.title("LightMap")
        self._root.resizable(True, False)
        self._root.columnconfigure(0, weight=1)
        self._root.protocol("WM_DELETE_WINDOW", on_close)
        self._closed = False

        content = ttk.Frame(self._root, padding=(20, 16))
        content.grid(sticky="ew")
        content.columnconfigure(0, weight=1)
        panel = ttk.LabelFrame(content, text="Playback", padding=12)
        panel.grid(row=0, column=0, sticky="ew")
        panel.columnconfigure((0, 1), weight=1)
        self._status = tk.StringVar(master=self._root, value="Stopped")
        ttk.Label(panel, text="Playback capture").grid(row=0, column=0, sticky="w")
        ttk.Label(panel, textvariable=self._status).grid(row=0, column=1, sticky="e")

        self._start_button = ttk.Button(panel, text="Start", command=on_start)
        self._start_button.grid(row=1, column=0, sticky="ew", pady=12, padx=(0, 6))
        self._stop_button = ttk.Button(panel, text="Stop", command=on_stop)
        self._stop_button.grid(row=1, column=1, sticky="ew", pady=12, padx=(6, 0))
        self._stop_button.state(["disabled"])

        self._overlay_enabled = tk.BooleanVar(master=self._root, value=False)
        self._overlay_button = ttk.Checkbutton(
            panel,
            text="Show overlay",
            variable=self._overlay_enabled,
            command=lambda: on_overlay_toggle(self._overlay_enabled.get()),
        )
        self._overlay_button.grid(row=2, column=0, columnspan=2, sticky="w")

        self._error = tk.StringVar(master=self._root)
        self._error_label = ttk.Label(panel, textvariable=self._error, wraplength=280)
        self._error_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self._error_label.grid_remove()
        self._settings_error = tk.StringVar(master=self._root)
        if palettes and current_palette is not None and on_palette_change is not None:
            self._build_palette_controls(content, palettes, current_palette, on_palette_change)
        if on_layout_change is not None:
            self._build_layout_controls(content, on_layout_change, on_smoothing_toggle)
        ttk.Label(content, textvariable=self._settings_error, wraplength=320).grid(
            row=3, column=0, sticky="w", pady=(8, 0)
        )
        self._poll_job = self._root.after(POLL_MS, self._apply_updates)

    def _build_palette_controls(self, content, palettes, current, on_change) -> None:
        panel = ttk.LabelFrame(content, text="Colour map", padding=12)
        panel.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        panel.columnconfigure(0, weight=1)
        choices = dict(palettes)
        active = next((name for name, path in choices.items() if path == current), None)
        if active is None:
            active = f"Custom: {current.name}"
            choices[active] = current
        self._palette = tk.StringVar(master=self._root, value=active)
        self._palette_picker = ttk.Combobox(
            panel, state="readonly", values=tuple(choices), textvariable=self._palette, width=23
        )
        self._palette_picker.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        def select(name: str, path: Path) -> None:
            nonlocal active
            try:
                on_change(path)
            except (OSError, ValueError) as exc:
                self._settings_error.set(str(exc))
                self._palette.set(active)
                return
            choices[name] = path
            self._palette_picker.configure(values=tuple(choices))
            active = name
            self._palette.set(name)
            self._settings_error.set("")

        def import_image() -> None:
            filename = filedialog.askopenfilename(
                parent=self._root,
                title="Import a colour map",
                filetypes=[("Palette images", "*.png *.jpg *.jpeg *.bmp *.webp"), ("All files", "*")],
            )
            if filename:
                path = Path(filename)
                select(f"Custom: {path.name}", path)

        def choose_palette(event) -> None:
            name = self._palette.get()
            select(name, choices[name])

        self._palette_picker.bind("<<ComboboxSelected>>", choose_palette)
        self._import_button = ttk.Button(panel, text="Import image…", command=import_image)
        self._import_button.grid(row=0, column=1)

    def _build_layout_controls(self, content, on_layout_change, on_smoothing_toggle) -> None:
        panel = ttk.LabelFrame(content, text="Overlay appearance", padding=12)
        panel.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(panel, text="Shape").grid(row=0, column=0, sticky="w")
        self._shape = tk.StringVar(master=self._root, value="Bar")
        self._shape_picker = ttk.Combobox(
            panel, textvariable=self._shape, values=("Bar", "Circle"), state="readonly", width=10
        )
        self._shape_picker.grid(row=0, column=1, sticky="w")

        placement = ttk.Frame(panel)
        placement.grid(row=1, column=0, columnspan=2, sticky="w", pady=8)
        bar = ttk.Frame(placement)
        circle = ttk.Frame(placement)
        self._edge = tk.StringVar(master=self._root, value="Top")
        ttk.Label(bar, text="Edge").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            bar, textvariable=self._edge, values=[edge.title() for edge in EDGES],
            state="readonly", width=10,
        ).grid(row=0, column=1, padx=(8, 0))
        self._thickness = self._number_field(bar, "Thickness (px)", "48", 1, 1, 4096)
        self._radius = self._number_field(circle, "Radius (px)", "48", 0, 1, 4096)
        self._x_percent = self._number_field(circle, "Across (%)", "50", 1, 0, 100)
        self._y_percent = self._number_field(circle, "Down (%)", "15", 2, 0, 100)
        self._opacity = self._number_field(panel, "Opacity (%)", "100", 2, 1, 100)

        def switch_fields(event=None) -> None:
            if self._shape.get() == "Circle":
                bar.grid_remove()
                circle.grid(sticky="w")
            else:
                circle.grid_remove()
                bar.grid(sticky="w")

        self._shape_picker.bind("<<ComboboxSelected>>", switch_fields)
        switch_fields()
        if on_smoothing_toggle is not None:
            self._smoothing = tk.BooleanVar(master=self._root, value=True)
            self._smoothing_button = ttk.Checkbutton(
                panel, text="Smooth colour changes", variable=self._smoothing,
                command=lambda: on_smoothing_toggle(self._smoothing.get()),
            )
            self._smoothing_button.grid(row=3, column=0, columnspan=2, sticky="w", pady=8)

        def apply() -> None:
            bar_selected = self._shape.get() == "Bar"
            try:
                size = int(self._thickness.get() if bar_selected else self._radius.get())
                x = 50 if bar_selected else int(self._x_percent.get())
                y = 15 if bar_selected else int(self._y_percent.get())
                opacity = int(self._opacity.get())
            except ValueError:
                self._settings_error.set("Enter whole numbers for size, position and opacity.")
                return
            try:
                layout = OverlayLayout(self._shape.get().lower(), self._edge.get().lower(), size, x, y, opacity)
                on_layout_change(layout)
            except ValueError as exc:
                self._settings_error.set(str(exc))
                return
            self._settings_error.set("")

        self._layout_button = ttk.Button(panel, text="Apply layout", command=apply)
        self._layout_button.grid(row=4, column=0, columnspan=2, sticky="w")

    def _number_field(self, parent, label: str, default: str, row: int, low: int, high: int) -> tk.StringVar:
        value = tk.StringVar(master=self._root, value=default)
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w")
        ttk.Spinbox(parent, from_=low, to=high, textvariable=value, width=8).grid(
            row=row, column=1, sticky="w", padx=(8, 0), pady=2
        )
        return value

    def show(self) -> None:
        """Show the control window from its GUI thread."""
        self._root.deiconify()

    def run(self) -> None:
        """Process window events on the GUI thread until the window closes."""
        self._root.mainloop()

    def set_status(self, status: CaptureStatus) -> None:
        """Queue a status update, including calls from an audio worker."""
        if status not in ("stopped", "active", "error"):
            raise ValueError("capture status must be stopped, active, or error")
        self._updates.put(("status", status))

    def show_error(self, message: str) -> None:
        """Queue an error message for the control window."""
        self._updates.put(("error", message))

    def close(self) -> None:
        """Destroy the window from its GUI thread without invoking on_close."""
        if self._closed:
            return
        self._closed = True
        self._root.after_cancel(self._poll_job)
        self._root.destroy()

    def _apply_updates(self) -> None:
        while True:
            try:
                kind, value = self._updates.get_nowait()
            except Empty:
                break
            if kind == "error":
                self._error.set(value)
                self._error_label.grid()
                continue
            self._status.set(value.capitalize())
            active = value == "active"
            self._start_button.state(["disabled" if active else "!disabled"])
            self._stop_button.state(["!disabled" if active else "disabled"])
            if value != "error":
                self._error.set("")
                self._error_label.grid_remove()
        self._poll_job = self._root.after(POLL_MS, self._apply_updates)
