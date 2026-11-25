"""Drive the Tk controls and check the overlay state and rendered pixels."""

import sys
import threading
import time
from tkinter import TclError

import pytest

from lightmap import control_view
from lightmap.control_view import ControlView
from lightmap.overlay_layout import OverlayLayout


# --------------------------------------------------------------- ControlView

@pytest.fixture
def controls():
    calls = []
    try:
        view = ControlView(
            lambda: calls.append("start"),
            lambda: calls.append("stop"),
            calls.append,
            lambda: calls.append("close"),
        )
    except TclError as exc:
        if "display" in str(exc):
            pytest.skip(f"no display available for ControlView: {exc}")
        raise
    yield view, calls
    view.close()


def _control_updates(view):
    def drained():
        view._root.update()
        return view._updates.empty()

    assert _wait_until(drained)


def test_start_and_stop_controls_call_their_callbacks(controls):
    view, calls = controls
    assert view._root.state() == "withdrawn"
    view.show()
    view._stop_button.invoke()
    view._start_button.invoke()
    view.set_status("active")
    _control_updates(view)
    view._start_button.invoke()
    view._stop_button.invoke()
    assert calls == ["start", "stop"]


def test_overlay_toggle_passes_true_for_enabled_and_false_for_disabled(controls):
    view, calls = controls
    view._overlay_button.invoke()
    view._overlay_button.invoke()
    assert calls == [True, False]


def test_ca06_set_status_shows_each_of_the_three_states(controls):
    view, _ = controls
    assert view._status.get() == "Stopped"
    for status in ("active", "error", "stopped"):
        view.set_status(status)
        _control_updates(view)
        assert view._status.get() == status.capitalize()


def test_show_error_displays_the_message_from_the_audio_thread(controls):
    view, _ = controls
    view.show()

    def report_error():
        view.set_status("error")
        view.show_error("The output device was removed")

    worker = threading.Thread(target=report_error)
    worker.start()
    worker.join()
    _control_updates(view)
    assert view._status.get() == "Error"
    assert view._error.get() == "The output device was removed"
    assert view._error_label.winfo_ismapped()
    view.set_status("active")
    _control_updates(view)
    assert not view._error_label.winfo_ismapped()


def test_close_releases_the_window_without_calling_on_close_again(controls):
    view, calls = controls
    view._root.tk.call(view._root.protocol("WM_DELETE_WINDOW"))
    view.close()
    view.close()
    assert calls == ["close"]
    with pytest.raises(TclError):
        view._root.winfo_exists()


def test_settings_controls_change_palette_smoothing_and_layout(tmp_path, monkeypatch):
    calls = []
    palette = tmp_path / "spectrum.png"
    ember = tmp_path / "ember.png"
    custom = tmp_path / "custom.png"
    monkeypatch.setattr(control_view.filedialog, "askopenfilename", lambda **kwargs: str(custom))
    try:
        view = ControlView(
            lambda: None, lambda: None, calls.append, lambda: None,
            palettes={"Spectrum": palette, "Ember": ember}, current_palette=palette,
            on_palette_change=calls.append, on_smoothing_toggle=calls.append,
            on_layout_change=calls.append,
        )
    except TclError as exc:
        if "display" in str(exc):
            pytest.skip(f"no display available for ControlView: {exc}")
        raise
    try:
        view.show()
        view._root.update()
        view._palette.set("Ember")
        view._palette_picker.event_generate("<<ComboboxSelected>>")
        view._import_button.invoke()
        view._smoothing_button.invoke()
        view._shape.set("Circle")
        view._shape_picker.event_generate("<<ComboboxSelected>>")
        view._radius.set("72")
        view._x_percent.set("100")
        view._y_percent.set("55")
        view._opacity.set("75")
        view._layout_button.invoke()
        assert calls == [ember, custom, False, OverlayLayout("circle", "top", 72, 100, 55, 75)]
        assert view._palette.get() == "Custom: custom.png"
        view._radius.set("zero")
        view._layout_button.invoke()
        assert view._settings_error.get()
        assert len(calls) == 4
    finally:
        view.close()


# --------------------------------------------------------------- OverlayView
# These drive a real Tk window, so they need a display (CI: xvfb-run pytest).
# Without one they skip instead of failing.

def _wait_until(condition, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


@pytest.fixture
def overlay():
    from lightmap.overlay_view import OverlayView

    try:
        view = OverlayView()
    except RuntimeError as exc:
        pytest.skip(f"no display available for OverlayView: {exc}")
    yield view
    view.close()


def _screen_pixel(x=100, y=10):
    from PIL import ImageGrab

    try:
        return ImageGrab.grab().getpixel((x, y))[:3]
    except Exception as exc:
        pytest.skip(f"cannot take a screenshot here: {exc}")


def test_overlay_starts_hidden_and_black(overlay):
    assert overlay.visible is False
    assert overlay.colour == (0, 0, 0)


def test_d01_set_colour_changes_the_colour_but_not_the_visibility(overlay):
    overlay.set_colour((10, 20, 30))
    assert overlay.colour == (10, 20, 30)
    assert overlay.visible is False
    overlay.show()
    overlay.set_colour((200, 100, 50))
    assert overlay.colour == (200, 100, 50)
    assert overlay.visible is True


def test_d01_last_colour_wins(overlay):
    overlay.set_colour((255, 0, 0))
    overlay.set_colour((0, 255, 0))
    assert overlay.colour == (0, 255, 0)


@pytest.mark.parametrize(
    "bad",
    [(1, 2), (1, 2, 3, 4), (256, 0, 0), (-1, 0, 0), (1.5, 0, 0), (True, 0, 0), [1, 2, 3], "red"],
)
def test_set_colour_rejects_invalid_colours_and_keeps_the_old_one(overlay, bad):
    overlay.set_colour((5, 6, 7))
    with pytest.raises(ValueError):
        overlay.set_colour(bad)
    assert overlay.colour == (5, 6, 7)


def test_d03_d04_show_and_hide_change_visibility(overlay):
    overlay.show()
    assert overlay.visible is True
    overlay.hide()
    assert overlay.visible is False
    overlay.show()
    overlay.show()
    assert overlay.visible is True


def test_d04_colour_sent_while_hidden_is_shown_after_reenable(overlay):
    overlay.show()
    overlay.hide()
    overlay.set_colour((9, 99, 199))
    assert overlay.visible is False
    overlay.show()
    assert overlay.colour == (9, 99, 199)


def test_d01_screen_pixels_match_the_commanded_colour(overlay):
    """Automated version of the screenshot check (tolerance +-2 per channel)."""
    for colour in [(255, 0, 0), (12, 200, 99), (3, 3, 250)]:
        overlay.set_colour(colour)
        overlay.show()
        assert _wait_until(
            lambda: all(abs(a - b) <= 2 for a, b in zip(_screen_pixel(), colour))
        ), f"screen pixel {_screen_pixel()} does not match {colour}"


def test_d04_hidden_overlay_draws_nothing(overlay):
    overlay.set_colour((255, 0, 0))
    overlay.show()
    assert _wait_until(lambda: _screen_pixel() == (255, 0, 0))
    overlay.hide()
    assert _wait_until(lambda: _screen_pixel() != (255, 0, 0))


@pytest.mark.parametrize(
    ("edge", "bounds"),
    [("top", (600, 24, 0, 0)), ("bottom", (600, 24, 0, 376)),
     ("left", (24, 400, 0, 0)), ("right", (24, 400, 576, 0))],
)
def test_bar_layout_matches_requested_edge_and_thickness(edge, bounds):
    assert OverlayLayout(edge=edge, size=24).bounds(600, 400) == bounds


def test_circle_position_uses_available_screen_space():
    layout = OverlayLayout("circle", size=25, x_percent=100, y_percent=50)
    assert layout.bounds(600, 400) == (50, 50, 550, 175)
    assert OverlayLayout("circle", size=500).bounds(600, 400)[:2] == (400, 400)
    with pytest.raises(ValueError, match="Position"):
        OverlayLayout("circle", x_percent=120)


@pytest.mark.skipif(sys.platform != "win32", reason="native overlay regions require Windows")
def test_switching_circle_to_bar_updates_the_rendered_region(overlay):
    colour = (233, 90, 179)
    overlay.set_layout(OverlayLayout("circle", size=35, x_percent=0, y_percent=0))
    overlay.set_colour(colour)
    overlay.show()
    assert _wait_until(lambda: _screen_pixel(35, 35) == colour)
    assert _screen_pixel(2, 2) != colour
    overlay.set_layout(OverlayLayout(size=70))
    assert _wait_until(lambda: _screen_pixel(2, 2) == colour)


def test_calls_from_other_threads_are_safe(overlay):
    def hammer():
        for i in range(200):
            overlay.set_colour((i % 256, 0, 0))
            overlay.show() if i % 2 else overlay.hide()

    threads = [threading.Thread(target=hammer) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    overlay.set_colour((1, 2, 3))
    assert overlay.colour == (1, 2, 3)


def test_d05_close_releases_the_overlay(overlay):
    overlay.show()
    overlay.close()
    assert overlay.closed is True
    assert overlay.visible is False
    assert not any(t.name == "OverlayView" for t in threading.enumerate())


def test_d05_close_twice_and_use_after_close_do_nothing(overlay):
    overlay.close()
    overlay.close()
    overlay.set_colour((1, 1, 1))
    overlay.show()
    overlay.hide()
    assert overlay.closed is True
    assert overlay.visible is False
