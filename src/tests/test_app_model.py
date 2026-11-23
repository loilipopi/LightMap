"""AppModel tests (owner: Kevin).

Requirements covered: CA-06 (capture status), D-01 (latest colour is stored).
"""

import pytest

from lightmap.app_model import AppModel


def test_initial_state():
    model = AppModel()
    assert model.capture_status == "stopped"
    assert model.settings == {}
    assert model.output_colour == (0, 0, 0)
    assert model.overlay_enabled is False


@pytest.mark.parametrize("status", ["stopped", "active", "error"])
def test_status_holds_each_of_the_three_states(status):
    model = AppModel()
    model.capture_status = status
    assert model.capture_status == status


@pytest.mark.parametrize("status", ["banana", "Active", None, 1])
def test_status_rejects_values_other_than_the_three_states(status):
    model = AppModel()
    with pytest.raises((ValueError, TypeError)):
        model.capture_status = status
    assert model.capture_status == "stopped"


def test_latest_colour_replaces_the_previous_one():
    model = AppModel()
    model.output_colour = (1, 2, 3)
    model.output_colour = (4, 5, 6)
    assert model.output_colour == (4, 5, 6)


@pytest.mark.parametrize(
    "colour", [(0, 1), (0, 0, 256), (-1, 0, 0), (0.5, 0, 0), (True, 0, 0)]
)
def test_invalid_colour_preserves_previous_value(colour):
    model = AppModel()
    model.output_colour = (0, 255, 0)
    with pytest.raises(ValueError):
        model.output_colour = colour
    assert model.output_colour == (0, 255, 0)


def test_overlay_enabled_accepts_only_booleans():
    model = AppModel()
    model.overlay_enabled = True
    assert model.overlay_enabled is True
    with pytest.raises(TypeError):
        model.overlay_enabled = 1
    assert model.overlay_enabled is True
    model.overlay_enabled = False
    assert model.overlay_enabled is False


def test_models_do_not_share_state():
    """Catches a mutable default shared between instances."""
    a = AppModel()
    b = AppModel()
    a.settings["gain"] = 2.0
    assert b.settings == {}
