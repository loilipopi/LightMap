import tkinter as tk
from queue import Empty, SimpleQueue
from tkinter import ttk
from typing import Callable

from .app_model import CaptureStatus

POLL_MS = 20


class ControlView:
    """Show playback controls on the GUI thread and accept worker updates."""

    def __init__(
        self,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_overlay_toggle: Callable[[bool], None],
        on_close: Callable[[], None],
    ) -> None:
        """Create a hidden window with the controller's callbacks attached."""
        self._updates: SimpleQueue[tuple[str, str]] = SimpleQueue()
        self._root = tk.Tk()
        self._root.withdraw()
        self._root.title("LightMap")
        self._root.resizable(False, False)
        self._root.protocol("WM_DELETE_WINDOW", on_close)
        self._closed = False

        panel = ttk.Frame(self._root, padding=(20, 16))
        panel.grid()
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
        self._poll_job = self._root.after(POLL_MS, self._apply_updates)

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
