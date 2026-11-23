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

@pytest.mark.skip(reason=NEEDS_VIEW_HOOKS)
def test_overlay_starts_hidden_and_black():
    """A new OverlayView is hidden and its colour is (0, 0, 0)."""


@pytest.mark.skip(reason=NEEDS_VIEW_HOOKS)
def test_d01_set_colour_changes_the_colour_but_not_the_visibility():
    """set_colour((r, g, b)) updates the colour; hidden stays hidden, shown stays shown."""


@pytest.mark.skip(reason=NEEDS_VIEW_HOOKS)
def test_d03_d04_show_and_hide_change_visibility():
    """show() makes it visible with its current colour; hide() hides it."""


@pytest.mark.skip(reason=NEEDS_VIEW_HOOKS)
def test_d05_close_releases_the_overlay():
    """After close() the overlay is gone and its resources are released."""
