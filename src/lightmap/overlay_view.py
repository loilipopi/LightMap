"""OverlayView: a borderless, always-on-top colour bar shown along the top
edge of the screen.

Threading: the controller calls this view from the audio-callback thread and
from the GUI thread, but tkinter widgets may only be touched by the thread
that created them. So the view owns a private UI thread running its own Tk
root. The public methods only update a small lock-protected "desired state"
(colour, visible, closed); the UI thread applies it every POLL_MS. That
makes every method safe to call from any thread, never blocks the audio
thread on drawing, and gives last-colour-wins for free.
"""

import gc
import sys
import threading
import tkinter as tk
from numbers import Integral

RGB = tuple[int, int, int]

BAR_HEIGHT = 48        # pixels; the bar spans the full screen width
POLL_MS = 15           # how often the UI thread applies the desired state
RAISE_MS = 500         # while visible, re-assert "always on top" this often
START_TIMEOUT_S = 5.0
CLOSE_TIMEOUT_S = 2.0


def _validate_colour(colour: RGB) -> RGB:
    if not isinstance(colour, tuple) or len(colour) != 3 or any(
        isinstance(channel, bool)
        or not isinstance(channel, Integral)
        or not 0 <= channel <= 255
        for channel in colour
    ):
        raise ValueError("colour must be an RGB tuple with channels from 0 to 255")
    red, green, blue = colour
    return (int(red), int(green), int(blue))


class OverlayView:
    def __init__(self) -> None:
        """
        Preconditions:
            None.
        Postconditions:
            The overlay is hidden and its colour is black.
        Raises:
            RuntimeError if no display is available.
        """
        self._lock = threading.Lock()
        self._colour: RGB = (0, 0, 0)
        self._visible = False
        self._closed = False
        self._ready = threading.Event()
        self._startup_error: BaseException | None = None
        self._thread = threading.Thread(
            target=self._run, name="OverlayView", daemon=True
        )
        self._thread.start()
        if not self._ready.wait(START_TIMEOUT_S):
            raise RuntimeError("the overlay window did not start")
        if self._startup_error is not None:
            raise RuntimeError(
                f"could not create the overlay window: {self._startup_error}"
            ) from self._startup_error

    # ------------------------------------------------------------ read-only state

    @property
    def colour(self) -> RGB:
        """The colour the overlay is set to (the latest one given)."""
        with self._lock:
            return self._colour

    @property
    def visible(self) -> bool:
        """Whether the overlay has been asked to be visible."""
        with self._lock:
            return self._visible and not self._closed

    @property
    def closed(self) -> bool:
        """Whether close() has been called."""
        with self._lock:
            return self._closed

    # ------------------------------------------------------------ public commands

    def set_colour(self, colour: tuple[int, int, int]) -> None:
        """
        Preconditions:
            colour contains three integers from 0 to 255.
        Postconditions:
            The overlay's colour is set to colour (rendered screen
            pixels match within +/-2 per RGB channel in overlay
            screenshots).
            Its visibility is unchanged.
        """
        colour = _validate_colour(colour)
        with self._lock:
            if not self._closed:
                self._colour = colour

    def show(self) -> None:
        """
        Preconditions:
            None.
        Postconditions:
            The overlay is visible and displays its current colour.
        """
        with self._lock:
            if not self._closed:
                self._visible = True

    def hide(self) -> None:
        """
        Preconditions:
            None.
        Postconditions:
            The overlay is hidden.
        """
        with self._lock:
            if not self._closed:
                self._visible = False

    def close(self) -> None:
        """
        Preconditions:
            None.
        Postconditions:
            The overlay is closed and its resources are released.
            Calling it again does nothing.
        """
        with self._lock:
            self._closed = True
        if threading.current_thread() is not self._thread:
            self._thread.join(CLOSE_TIMEOUT_S)

    # ------------------------------------------------------------ UI thread

    def _run(self) -> None:
        """Own the Tk root: create it, apply the desired state, destroy it."""
        try:
            root = tk.Tk()
        except Exception as exc:  # no display, Tk missing, ...
            self._startup_error = exc
            self._ready.set()
            return

        apply = None
        try:
            root.withdraw()
            root.overrideredirect(True)          # no title bar or border
            root.attributes("-topmost", True)
            width = root.winfo_screenwidth()
            root.geometry(f"{width}x{BAR_HEIGHT}+0+0")
            root.configure(bg="#000000")
            self._make_click_through(root)

            state = {"colour": None, "visible": False, "raised_ms": 0}

            def apply() -> None:
                with self._lock:
                    colour, visible, closed = (
                        self._colour, self._visible, self._closed
                    )
                if closed:
                    root.destroy()
                    return
                if colour != state["colour"]:
                    root.configure(bg="#%02x%02x%02x" % colour)
                    state["colour"] = colour
                if visible != state["visible"]:
                    if visible:
                        root.deiconify()
                        root.attributes("-topmost", True)
                        root.lift()
                        state["raised_ms"] = 0
                    else:
                        root.withdraw()
                    state["visible"] = visible
                elif visible:
                    # Stay above windows that were raised after us.
                    state["raised_ms"] += POLL_MS
                    if state["raised_ms"] >= RAISE_MS:
                        root.attributes("-topmost", True)
                        root.lift()
                        state["raised_ms"] = 0
                root.after(POLL_MS, apply)

            root.after(POLL_MS, apply)
            self._ready.set()
            root.mainloop()
        except Exception as exc:
            if not self._ready.is_set():
                self._startup_error = exc
                self._ready.set()
        finally:
            # Drop every reference to Tk objects on this thread: if the main
            # thread garbage-collected them instead, Tcl would abort the process.
            root = apply = None
            gc.collect()
            with self._lock:
                self._closed = True
            self._ready.set()

    @staticmethod
    def _make_click_through(root: tk.Tk) -> None:
        """On Windows, let mouse clicks pass through to the windows below."""
        if sys.platform != "win32":
            return
        try:
            import ctypes

            root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            GWL_EXSTYLE = -20
            WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW = 0x80000, 0x20, 0x80
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE,
                style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW,
            )
        except Exception:
            pass  # purely a nicety; the overlay still works without it