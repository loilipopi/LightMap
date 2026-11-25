import tkinter as tk
from dataclasses import replace
from pathlib import Path
from queue import Empty, SimpleQueue
from threading import Lock
from tkinter import colorchooser, filedialog, ttk
from typing import Callable

from .app_model import CaptureStatus
from .overlay_layout import EDGES, POLYGONS, SHAPES, OverlayLayout
from .placement_preview import PlacementPreview
from .preferences import (
    MAX_EMPHASIS, MAX_FADE_MS, MAX_FLOOR_DB, MIN_FLOOR_DB,
    AppPreferences, AudioTuning, SmoothingTimes,
)

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
        on_smoothing_times_change: Callable[[SmoothingTimes], None] | None = None,
        on_layout_change: Callable[[OverlayLayout], None] | None = None,
        preferences: AppPreferences | None = None,
        on_preview_toggle: Callable[[bool], None] | None = None,
        on_audio_change: Callable[[AudioTuning], None] | None = None,
        on_idle_check: Callable[[], None] | None = None,
    ) -> None:
        """Create a hidden window with the controller's callbacks attached."""
        self._updates: SimpleQueue[tuple[str, str]] = SimpleQueue()
        self._level_lock = Lock()
        self._input_level: float | None = None
        self._meter_level: float | None = None
        self._on_idle_check = on_idle_check
        prefs = preferences or AppPreferences()
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

        self._overlay_enabled = tk.BooleanVar(master=self._root, value=prefs.overlay_enabled)
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
            self._build_layout_controls(content, prefs, on_layout_change, on_preview_toggle)
        if any(callback is not None for callback in (
            on_audio_change, on_smoothing_toggle, on_smoothing_times_change
        )):
            content.columnconfigure(1, weight=1)
            sidebar = ttk.Frame(content)
            sidebar.grid(row=0, column=1, rowspan=3, sticky="new", padx=(12, 0))
            sidebar.columnconfigure(0, weight=1)
            if on_audio_change is not None:
                self._build_audio_controls(sidebar, prefs.audio, on_audio_change)
            if on_smoothing_toggle is not None or on_smoothing_times_change is not None:
                self._build_smoothing_controls(sidebar, prefs, on_smoothing_toggle, on_smoothing_times_change)
        settings_label = ttk.Label(content, textvariable=self._settings_error, wraplength=500)
        settings_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
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

    def _build_layout_controls(self, content, prefs, on_layout_change, on_preview_toggle) -> None:
        panel = ttk.LabelFrame(content, text="Overlay appearance", padding=12)
        panel.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(panel, text="Shape").grid(row=0, column=0, sticky="w")
        layout = prefs.layout
        self._shape = tk.StringVar(master=self._root, value=layout.shape.title())
        self._shape_picker = ttk.Combobox(
            panel, textvariable=self._shape, values=[shape.title() for shape in SHAPES],
            state="readonly", width=12,
        )
        self._shape_picker.grid(row=0, column=1, sticky="w")

        placement = ttk.Frame(panel)
        placement.grid(row=1, column=0, columnspan=2, sticky="w", pady=8)
        bar = ttk.Frame(placement)
        floating = ttk.Frame(placement)
        circle = ttk.Frame(floating)
        polygon = ttk.Frame(floating)
        self._edge = tk.StringVar(master=self._root, value=layout.edge.title())
        ttk.Label(bar, text="Edge").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            bar, textvariable=self._edge, values=[edge.title() for edge in EDGES],
            state="readonly", width=10,
        ).grid(row=0, column=1, padx=(8, 0))
        self._thickness = self._number_field(
            bar, "Thickness (px)", str(layout.size if layout.shape == "bar" else 48), 1, 1, 4096
        )
        self._radius = self._number_field(
            circle, "Radius (px)", str(layout.size if layout.shape == "circle" else 48), 0, 1, 4096
        )
        width_label = tk.StringVar(master=self._root)
        self._shape_width = self._number_field(polygon, width_label, str(layout.width), 0, 1, 4096)
        self._shape_height = self._number_field(polygon, "Height (px)", str(layout.height), 1, 1, 4096)
        self._rotation = self._number_field(polygon, "Rotation (°)", str(layout.rotation), 2, -360, 360)
        self._x_percent = self._number_field(floating, "Across (%)", str(layout.x_percent), 1, 0, 100)
        self._y_percent = self._number_field(floating, "Down (%)", str(layout.y_percent), 2, 0, 100)
        self._opacity = self._number_field(panel, "Opacity (%)", str(layout.opacity), 2, 1, 100)
        applied_layout = layout

        def read_layout() -> OverlayLayout:
            shape = self._shape.get().lower()
            try:
                size = applied_layout.size
                if shape == "bar":
                    size = int(self._thickness.get())
                elif shape == "circle":
                    size = int(self._radius.get())
                x = applied_layout.x_percent if shape == "bar" else int(self._x_percent.get())
                y = applied_layout.y_percent if shape == "bar" else int(self._y_percent.get())
                opacity = int(self._opacity.get())
                width = int(self._shape_width.get()) if shape in POLYGONS else applied_layout.width
                height = int(self._shape_height.get()) if shape in POLYGONS else applied_layout.height
                rotation = int(self._rotation.get()) if shape in POLYGONS else applied_layout.rotation
            except ValueError as exc:
                raise ValueError("Enter whole numbers for the overlay fields.") from exc
            return OverlayLayout(
                shape=shape, edge=self._edge.get().lower(), size=size, x_percent=x, y_percent=y,
                opacity=opacity, width=width, height=height, rotation=rotation,
            )

        def checked_layout() -> OverlayLayout | None:
            try:
                return read_layout()
            except ValueError as exc:
                self._settings_error.set(str(exc))
                return None

        def commit_layout(layout: OverlayLayout) -> None:
            nonlocal applied_layout
            try:
                on_layout_change(layout)
            except ValueError as exc:
                self._settings_error.set(str(exc))
                return
            applied_layout = layout
            self._edge.set(layout.edge.title())
            self._x_percent.set(str(layout.x_percent))
            self._y_percent.set(str(layout.y_percent))
            self._placement.show_layout(layout)
            self._settings_error.set("")

        def switch_fields(event=None) -> None:
            shape = self._shape.get().lower()
            if shape == "bar":
                floating.grid_remove()
                bar.grid(sticky="w")
            else:
                bar.grid_remove()
                floating.grid(sticky="w")
                if shape == "circle":
                    polygon.grid_remove()
                    circle.grid(row=0, column=0, columnspan=2, sticky="w")
                else:
                    circle.grid_remove()
                    width_label.set({"triangle": "Base (px)", "rectangle": "Length (px)"}.get(shape, "Width (px)"))
                    polygon.grid(row=0, column=0, columnspan=2, sticky="w")
            try:
                self._placement.show_layout(read_layout())
            except ValueError:
                pass

        self._placement = PlacementPreview(panel, layout, checked_layout, commit_layout)
        self._shape_picker.bind("<<ComboboxSelected>>", switch_fields)
        switch_fields()

        def apply() -> None:
            layout = checked_layout()
            if layout is not None:
                commit_layout(layout)

        self._layout_button = ttk.Button(panel, text="Apply layout", command=apply)
        self._layout_button.grid(row=4, column=0, sticky="w")
        if on_preview_toggle is not None:
            preview_enabled = tk.BooleanVar(master=self._root, value=False)
            self._preview_button = ttk.Checkbutton(
                panel, text="Preview on desktop", variable=preview_enabled,
                command=lambda: on_preview_toggle(preview_enabled.get()),
            )
            self._preview_button.grid(row=4, column=1, sticky="w", padx=(12, 0))
        self._placement.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 3))
        ttk.Label(panel, text="Drag to place. Bars snap to an edge.").grid(
            row=6, column=0, columnspan=2, sticky="w"
        )

    def _build_smoothing_controls(self, sidebar, prefs, on_toggle, on_times_change) -> None:
        panel = ttk.LabelFrame(sidebar, text="Colour transitions", padding=12)
        panel.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        if on_toggle is not None:
            self._smoothing = tk.BooleanVar(master=self._root, value=prefs.smoothing)
            self._smoothing_button = ttk.Checkbutton(
                panel, text="Smooth colour changes", variable=self._smoothing,
                command=lambda: on_toggle(self._smoothing.get()),
            )
            self._smoothing_button.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        if on_times_change is None:
            return

        self._fade_in = self._number_field(
            panel, "Fade in (ms)", str(prefs.smoothing_times.fade_in_ms), 1, 0, MAX_FADE_MS
        )
        self._fade_out = self._number_field(
            panel, "Fade out (ms)", str(prefs.smoothing_times.fade_out_ms), 2, 0, MAX_FADE_MS
        )
        ttk.Label(panel, text="0 ms is instant. Higher values soften the change.", wraplength=225).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(4, 8)
        )

        def apply() -> None:
            try:
                fade_in, fade_out = int(self._fade_in.get()), int(self._fade_out.get())
            except ValueError:
                self._settings_error.set("Enter whole milliseconds for both fades.")
                return
            try:
                times = SmoothingTimes(fade_in, fade_out)
            except ValueError as exc:
                self._settings_error.set(str(exc))
                return
            on_times_change(times)
            self._settings_error.set("")

        self._smoothing_times_button = ttk.Button(panel, text="Apply timings", command=apply)
        self._smoothing_times_button.grid(row=4, column=0, columnspan=2, sticky="w")

    def _build_audio_controls(self, content, tuning, on_audio_change) -> None:
        panel = ttk.LabelFrame(content, text="Audio tuning", padding=12)
        panel.grid(row=0, column=0, sticky="ew")
        panel.columnconfigure(0, weight=1)
        self._applied_tuning = tuning
        self._meter_text = tk.StringVar(master=self._root, value="No signal")
        ttk.Label(panel, text="Input peak").grid(row=0, column=0, sticky="w")
        ttk.Label(panel, textvariable=self._meter_text).grid(row=0, column=1, sticky="e")
        self._meter = tk.Canvas(panel, width=220, height=14, highlightthickness=0)
        self._meter.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 10))
        self._meter.bind("<Configure>", lambda event: self._draw_meter())

        self._floor = tk.DoubleVar(master=self._root, value=tuning.floor_db)
        floor_text = tk.StringVar(master=self._root, value=f"{tuning.floor_db} dB")
        ttk.Label(panel, text="Noise floor").grid(row=2, column=0, sticky="w")
        ttk.Label(panel, textvariable=floor_text).grid(row=2, column=1, sticky="e")
        ttk.Scale(
            panel, from_=MIN_FLOOR_DB, to=MAX_FLOOR_DB, variable=self._floor,
            command=lambda value: floor_text.set(f"{round(float(value))} dB"),
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 2))
        ttk.Label(panel, text="Lower the floor to pick up quieter sounds.", wraplength=215).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )

        quiet = ttk.Frame(panel)
        quiet.grid(row=5, column=0, columnspan=2, sticky="ew")
        self._quiet_swatch = tk.Label(quiet, width=3, borderwidth=1, relief="solid")
        self._quiet_swatch.grid(row=0, column=1, padx=(8, 0))
        self._quiet_swatch.configure(background="#%02x%02x%02x" % tuning.quiet_colour)

        bands = ttk.LabelFrame(panel, text="Frequency emphasis", padding=8)
        bands.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(12, 8))
        self._low_band = self._number_field(bands, "Low (<250 Hz) %", str(tuning.low), 0, 0, MAX_EMPHASIS)
        self._mid_band = self._number_field(bands, "Mid (250–3999 Hz) %", str(tuning.mid), 1, 0, MAX_EMPHASIS)
        self._high_band = self._number_field(bands, "High (≥4000 Hz) %", str(tuning.high), 2, 0, MAX_EMPHASIS)
        ttk.Label(bands, text="100% is neutral. 0% mutes a band.", wraplength=212).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )

        def commit(audio: AudioTuning) -> None:
            on_audio_change(audio)
            self._applied_tuning = audio
            self._quiet_swatch.configure(background="#%02x%02x%02x" % audio.quiet_colour)
            self._draw_meter()
            self._settings_error.set("")

        def choose_quiet_colour() -> None:
            rgb, _ = colorchooser.askcolor(
                color="#%02x%02x%02x" % self._applied_tuning.quiet_colour,
                parent=self._root, title="Choose the quiet colour",
            )
            if rgb is not None:
                commit(replace(self._applied_tuning, quiet_colour=tuple(round(channel) for channel in rgb)))

        def apply() -> None:
            try:
                gains = [int(field.get()) for field in (self._low_band, self._mid_band, self._high_band)]
            except ValueError:
                self._settings_error.set("Enter whole percentages for the three bands.")
                return
            try:
                audio = AudioTuning(round(self._floor.get()), self._applied_tuning.quiet_colour, *gains)
            except ValueError as exc:
                self._settings_error.set(str(exc))
                return
            commit(audio)

        self._quiet_button = ttk.Button(quiet, text="Quiet colour…", command=choose_quiet_colour)
        self._quiet_button.grid(row=0, column=0, sticky="w")
        self._audio_button = ttk.Button(panel, text="Apply tuning", command=apply)
        self._audio_button.grid(row=7, column=0, columnspan=2, sticky="w")

    def _draw_meter(self) -> None:
        width, height = self._meter.winfo_width(), self._meter.winfo_height()
        level, floor = self._meter_level, self._applied_tuning.floor_db
        self._meter.delete("all")
        self._meter.create_rectangle(0, 0, width, height, fill="#202832", outline="")
        if level is not None:
            fill = width * min(max((level - MIN_FLOOR_DB) / -MIN_FLOOR_DB, 0), 1)
            self._meter.create_rectangle(0, 0, fill, height, fill="#72cce4", outline="")
        marker = width * (floor - MIN_FLOOR_DB) / -MIN_FLOOR_DB
        self._meter.create_line(max(1, marker), 0, max(1, marker), height, fill="#ffbc6c", width=2)
        self._meter_text.set(
            "No signal" if level is None else f"{level:.0f} dB" + (" · below floor" if level < floor else "")
        )

    def _number_field(
        self, parent, label: str | tk.StringVar, default: str, row: int, low: int, high: int
    ) -> tk.StringVar:
        value = tk.StringVar(master=self._root, value=default)
        description = (ttk.Label(parent, text=label) if isinstance(label, str)
                       else ttk.Label(parent, textvariable=label))
        description.grid(row=row, column=0, sticky="w")
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

    def show_settings_notice(self, message: str) -> None:
        """Display a settings or recovery issue on the control window."""
        self._updates.put(("settings", message))

    def set_input_level(self, level: float | None) -> None:
        """Keep only the newest peak reading from the capture thread."""
        with self._level_lock:
            self._input_level = level

    def close(self) -> None:
        """Destroy the window from its GUI thread without invoking on_close."""
        if self._closed:
            return
        self._closed = True
        self._root.after_cancel(self._poll_job)
        self._root.destroy()

    def _apply_updates(self) -> None:
        if self._on_idle_check is not None:
            self._on_idle_check()
        with self._level_lock:
            level = self._input_level
        if level != self._meter_level:
            self._meter_level = level
            if hasattr(self, "_meter"):
                self._draw_meter()
        while True:
            try:
                kind, value = self._updates.get_nowait()
            except Empty:
                break
            if kind == "settings":
                self._settings_error.set(value)
                continue
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
