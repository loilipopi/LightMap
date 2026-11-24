"""ControlView and OverlayView tests (owners: Robert and Lucas).

Requirements covered once written: CA-06, D-01, D-03, D-04, D-05.

Everything here is a skipped placeholder, on purpose. The view stubs have no
way to read their state back (no getters for the shown status, visibility or
colour), and the GUI toolkit is not chosen yet, so there is nothing a test can
check. Each placeholder records the pass criterion from the checklist, so
nothing gets forgotten. To enable one: expose the state (or drive the widgets
through the toolkit's test hooks), delete the skip marker and write the body.

The behaviour that routes through the views (status shown, overlay shown or
hidden, closed on exit) is already covered from the controller's side in
test_app_controller.py. Pixel-level checks stay manual (within +-2 per RGB
channel in overlay screenshots; see the checklist).
"""

import time

import pytest

NEEDS_VIEW_HOOKS = (
    "The view stubs expose no state and the GUI toolkit isn't chosen yet; "
    "see the note at the top of this file."
)


# --------------------------------------------------------------- ControlView

@pytest.mark.skip(reason=NEEDS_VIEW_HOOKS)
def test_start_and_stop_controls_call_their_callbacks():
    """Activating Start calls on_start exactly once; Stop calls on_stop once."""


@pytest.mark.skip(reason=NEEDS_VIEW_HOOKS)
def test_overlay_toggle_passes_true_for_enabled_and_false_for_disabled():
    """on_overlay_toggle(True) when enabled, on_overlay_toggle(False) when disabled."""


@pytest.mark.skip(reason=NEEDS_VIEW_HOOKS)
def test_ca06_set_status_shows_each_of_the_three_states():
    """After set_status('stopped' / 'active' / 'error') the displayed text
    matches the status. A new ControlView shows 'stopped'."""


@pytest.mark.skip(reason=NEEDS_VIEW_HOOKS)
def test_show_error_displays_the_message():
    """show_error(message) makes the message visible to the user."""


@pytest.mark.skip(reason=NEEDS_VIEW_HOOKS)
def test_close_releases_the_window_without_calling_on_close_again():
    """close() closes the window and does not invoke on_close."""


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


def test_calls_from_other_threads_are_safe(overlay):
    import threading

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
    import threading

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