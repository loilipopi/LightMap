"""Drive the Tk controls and check the overlay state and rendered pixels."""

import sys
import threading
import time
from tkinter import TclError

import pytest

from lightmap import control_view
from lightmap.control_view import ControlView
from lightmap.overlay_layout import OverlayLayout
from lightmap.preferences import AppPreferences, AudioTuning, SmoothingTimes


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


def test_remembered_controls_drag_and_apply_audio_tuning(monkeypatch):
    placed, tuning, preview = [], [], []
    prefs = AppPreferences(
        smoothing=False, overlay_enabled=True, layout=OverlayLayout(edge="bottom", size=30),
        audio=AudioTuning(-54, (13, 15, 17), 120, 80, 60),
    )
    monkeypatch.setattr(
        control_view.colorchooser, "askcolor", lambda **kwargs: ((45, 90, 125), "#2d5a7d")
    )
    try:
        view = ControlView(
            lambda: None, lambda: None, lambda enabled: None, lambda: None,
            on_smoothing_toggle=lambda enabled: None, on_layout_change=placed.append,
            on_preview_toggle=preview.append, on_audio_change=tuning.append, preferences=prefs,
        )
    except TclError as exc:
        if "display" in str(exc):
            pytest.skip(f"no display available for ControlView: {exc}")
        raise
    try:
        view.show()
        view._root.update()
        assert view._overlay_enabled.get() and not view._smoothing.get()
        assert view._edge.get() == "Bottom" and view._thickness.get() == "30"
        assert view._floor.get() == -54 and view._low_band.get() == "120"
        view._preview_button.invoke()
        assert preview == [True]

        canvas = view._placement
        left, top, scale = canvas._viewport()
        screen_width, screen_height = canvas._screen_width, canvas._screen_height
        canvas.event_generate("<ButtonPress-1>", x=round(left + screen_width * scale / 2),
                              y=round(top + (screen_height - 10) * scale))
        x, y = round(left + (screen_width - 6) * scale), round(top + screen_height * scale / 2)
        canvas.event_generate("<B1-Motion>", x=x, y=y)
        canvas.event_generate("<ButtonRelease-1>", x=x, y=y)
        assert placed == [OverlayLayout(edge="right", size=30)]
        assert view._edge.get() == "Right"

        view._quiet_button.invoke()
        assert tuning == [AudioTuning(-54, (45, 90, 125), 120, 80, 60)]
        view._floor.set(-72)
        view._mid_band.set("250")
        view._audio_button.invoke()
        assert tuning[-1] == AudioTuning(-72, (45, 90, 125), 120, 250, 60)
        view.set_input_level(-35.6)

        def meter_updated():
            view._root.update()
            return view._meter_text.get() == "-36 dB"

        assert _wait_until(meter_updated)
    finally:
        view.close()


def test_gui_applies_custom_timings_and_polygon_dimensions():
    layouts, timings = [], []
    prefs = AppPreferences(
        layout=OverlayLayout("rectangle", width=150, height=32, rotation=15),
        smoothing_times=SmoothingTimes(5, 120),
    )
    try:
        view = ControlView(
            lambda: None, lambda: None, lambda enabled: None, lambda: None,
            preferences=prefs, on_layout_change=layouts.append,
            on_smoothing_times_change=timings.append,
        )
    except TclError as exc:
        if "display" in str(exc):
            pytest.skip(f"no display available for ControlView: {exc}")
        raise
    try:
        view.show()
        view._root.update()
        assert view._shape.get() == "Rectangle"
        assert view._shape_width.get() == "150" and view._rotation.get() == "15"
        assert view._fade_in.get() == "5" and view._fade_out.get() == "120"

        view._fade_in.set("0")
        view._fade_out.set("340")
        view._smoothing_times_button.invoke()
        assert timings == [SmoothingTimes(0, 340)]
        view._fade_in.set("-1")
        view._smoothing_times_button.invoke()
        assert len(timings) == 1 and view._settings_error.get()

        view._shape.set("Triangle")
        view._shape_picker.event_generate("<<ComboboxSelected>>")
        view._shape_width.set("125")
        view._shape_height.set("95")
        view._rotation.set("-42")
        view._layout_button.invoke()
        assert layouts == [OverlayLayout("triangle", width=125, height=95, rotation=-42)]
        canvas = view._placement
        assert canvas.type(canvas.find_all()[-1]) == "polygon"
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


def test_dragging_a_circle_preserves_grab_offset_and_clamps_to_display():
    layout = OverlayLayout("circle", size=50, x_percent=20, y_percent=20)
    assert layout.placed_at(500, 400, 320, 250, (20, 40)).bounds(500, 400) == (100, 100, 300, 210)
    assert layout.placed_at(500, 400, 1000, -80).bounds(500, 400) == (100, 100, 400, 0)


def test_rotated_rectangle_dimensions_and_dragging_at_screen_edges():
    layout = OverlayLayout("rectangle", width=200, height=60, rotation=90)
    assert layout.bounds(800, 600)[:2] == (60, 200)
    moved = layout.placed_at(800, 600, 900, 800)
    assert moved.bounds(800, 600) == (60, 200, 740, 400)
    assert moved.rotation == 90 and moved.width == 200 and moved.height == 60


@pytest.mark.parametrize(("shape", "corners"), [("triangle", 3), ("diamond", 4), ("hexagon", 6)])
def test_oversized_rotated_shapes_fit_and_share_window_local_vertices(shape, corners):
    layout = OverlayLayout(shape, width=1200, height=1000, rotation=37)
    geometry = layout.geometry(180, 100)
    width, height, x, y = geometry.bounds
    assert x >= 0 and y >= 0 and x + width <= 180 and y + height <= 100
    assert len(geometry.polygon) == corners
    assert all(0 <= px <= width + 1e-9 and 0 <= py <= height + 1e-9 for px, py in geometry.polygon)


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


@pytest.mark.skipif(sys.platform != "win32", reason="native overlay regions require Windows")
@pytest.mark.parametrize("shape", ["rectangle", "triangle", "diamond", "hexagon"])
def test_desktop_renders_rotated_shape_with_transparent_corners(overlay, shape):
    layout = OverlayLayout(shape, width=145, height=78, rotation=37, x_percent=0, y_percent=0)
    geometry = layout.geometry(800, 600)
    middle = tuple(round(sum(axis) / len(axis)) for axis in zip(*geometry.polygon))
    colour = (231, 42, 171)
    overlay.set_layout(layout)
    overlay.set_colour(colour)
    overlay.show()
    assert _wait_until(lambda: _screen_pixel(*middle) == colour)
    corners = [(2, 2), (geometry.bounds[0] - 2, 2)]
    assert any(_screen_pixel(*point) != colour for point in corners)


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
