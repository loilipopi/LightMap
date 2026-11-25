"""A borderless, always-on-top colour overlay on the primary display.

Threading: the controller calls this view from the audio-callback thread and
from the GUI thread, but tkinter widgets may only be touched by the thread
that created them. So the view owns a private UI thread running its own Tk
root. The public methods only update a small lock-protected "desired state"
(colour, visible, closed); the UI thread applies it every POLL_MS. That
makes every method safe to call from any thread, never blocks the audio
thread on drawing, and gives last-colour-wins for free.
"""

import sys
import threading
import tkinter as tk
from numbers import Integral

from .overlay_layout import OverlayGeometry, OverlayLayout

RGB = tuple[int, int, int]

POLL_MS = 4            # how often the UI thread applies the desired state
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
        self._layout = OverlayLayout()
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

    def set_layout(self, layout: OverlayLayout) -> None:
        """Set shape, placement, size and opacity without showing the window."""
        if layout.shape != "bar" and sys.platform != "win32":
            raise ValueError("Shaped overlays require Windows.")
        with self._lock:
            if not self._closed:
                self._layout = layout

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
        hi_res_timer = False
        try:
            if sys.platform == "win32":
                hi_res_timer = self._set_windows_timer_resolution(True)
            root.withdraw()
            root.overrideredirect(True)          # no title bar or border
            root.attributes("-topmost", True)
            root.configure(bg="#000000")

            state = {"colour": None, "visible": False, "raised_ms": 0}
            applied_layout = None

            def apply() -> None:
                nonlocal applied_layout
                with self._lock:
                    colour, visible, closed, layout = (
                        self._colour, self._visible, self._closed, self._layout
                    )
                if closed:
                    root.quit()
                    return
                if colour != state["colour"]:
                    root.configure(bg="#%02x%02x%02x" % colour)
                    state["colour"] = colour
                if layout != applied_layout:
                    self._apply_layout(root, layout)
                    applied_layout = layout
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
            if hi_res_timer:
                self._set_windows_timer_resolution(False)
            # Destroy the interpreter's window here and break the poll callback's
            # self-reference. Collecting globally here can finalize the control
            # window's Tk objects on the wrong thread.
            try:
                root.destroy()
            except tk.TclError:
                pass
            root = apply = None
            with self._lock:
                self._closed = True
            self._ready.set()

    @staticmethod
    def _set_windows_timer_resolution(enable: bool) -> bool:
        """Request 1 ms Windows timer resolution so 4 ms polling isn't quantized to 15.6 ms."""
        try:
            import ctypes

            winmm = ctypes.windll.winmm
            fn = winmm.timeBeginPeriod if enable else winmm.timeEndPeriod
            return fn(1) == 0
        except Exception:
            return False

    @staticmethod
    def _apply_layout(root: tk.Tk, layout: OverlayLayout) -> None:
        geometry = layout.geometry(root.winfo_screenwidth(), root.winfo_screenheight())
        width, height, x, y = geometry.bounds
        root.geometry(f"{width}x{height}+{x}+{y}")
        if sys.platform != "win32":
            root.attributes("-alpha", layout.opacity / 100)
            return
        root.update_idletasks()
        OverlayView._configure_windows(root.winfo_id(), geometry, layout)

    @staticmethod
    def _configure_windows(window: int, geometry: OverlayGeometry, layout: OverlayLayout) -> None:
        """Set click-through, opacity and the native drawing region."""
        import ctypes
        from ctypes import wintypes

        user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
        user32.GetParent.argtypes = (wintypes.HWND,)
        user32.GetParent.restype = wintypes.HWND
        user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
        user32.SetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.LONG)
        user32.SetLayeredWindowAttributes.argtypes = (
            wintypes.HWND, wintypes.COLORREF, wintypes.BYTE, wintypes.DWORD
        )
        user32.SetWindowRgn.argtypes = (wintypes.HWND, wintypes.HRGN, wintypes.BOOL)
        gdi32.CreateEllipticRgn.argtypes = (ctypes.c_int,) * 4
        gdi32.CreateEllipticRgn.restype = wintypes.HRGN
        gdi32.CreatePolygonRgn.argtypes = (
            ctypes.POINTER(wintypes.POINT), ctypes.c_int, ctypes.c_int
        )
        gdi32.CreatePolygonRgn.restype = wintypes.HRGN
        gdi32.DeleteObject.argtypes = (wintypes.HGDIOBJ,)

        hwnd = user32.GetParent(window) or window
        GWL_EXSTYLE = -20
        WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW = 0x80000, 0x20, 0x80
        LWA_ALPHA = 0x02
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
        )
        if not user32.SetLayeredWindowAttributes(hwnd, 0, round(layout.opacity * 255 / 100), LWA_ALPHA):
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        width, height, _, _ = geometry.bounds
        region = None
        if layout.shape == "circle":
            region = gdi32.CreateEllipticRgn(0, 0, width, height)
        elif geometry.polygon and width > 1 and height > 1:
            vertices = tuple(dict.fromkeys((round(x), round(y)) for x, y in geometry.polygon))
            if len(vertices) >= 3:
                points = (wintypes.POINT * len(vertices))(
                    *(wintypes.POINT(x, y) for x, y in vertices)
                )
                region = gdi32.CreatePolygonRgn(points, len(points), 2)  # WINDING fill rule
        if not user32.SetWindowRgn(hwnd, region, True) and region:
            # Windows owns the region only after a successful call.
            gdi32.DeleteObject(region)
