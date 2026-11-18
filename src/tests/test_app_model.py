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


@pytest.mark.parametrize("status", ["stopped", "active", "error"])
def test_status_holds_each_of_the_three_states(status):
    model = AppModel()
    model.capture_status = status
    assert model.capture_status == status


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CA-06: capture_status is a plain str, so nothing stops it holding a "
        "fourth value. Add validation (a property setter or an Enum), then "
        "delete this marker. strict=True makes the test fail once it starts "
        "passing, so you cannot forget to remove it."
    ),
)
def test_status_rejects_values_other_than_the_three_states():
    model = AppModel()
    with pytest.raises((ValueError, TypeError)):
        model.capture_status = "banana"


def test_latest_colour_replaces_the_previous_one():
    model = AppModel()
    model.output_colour = (1, 2, 3)
    model.output_colour = (4, 5, 6)
    assert model.output_colour == (4, 5, 6)


def test_models_do_not_share_state():
    """Catches a mutable default shared between instances."""
    a = AppModel()
    b = AppModel()
    a.settings["gain"] = 2.0
    assert b.settings == {}
