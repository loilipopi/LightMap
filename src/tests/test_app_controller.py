"""AppController tests (owner: Kevin).

Requirements covered: CA-03, CA-05, CA-06, CA-07, CA-08, D-01, D-03, D-04, D-05.

Uses a real AppModel and the fakes from conftest.py for everything else.
Convention: FakeMapper turns a spectrum with k pairs into the colour (k, 0, 0).
"""

import pytest

SPECTRUM_1 = [(100.0, 1.0)]                    # -> colour (1, 0, 0)
SPECTRUM_2 = [(100.0, 1.0), (200.0, 2.0)]      # -> colour (2, 0, 0)
SAMPLES = [0.0] * 8
RATE = 48000


# ------------------------------------------------------------- set_views

@pytest.mark.parametrize("status", ["stopped", "active", "error"])
def test_set_views_shows_the_models_status(make_parts, status):
    p = make_parts(attach=False)
    p.model.capture_status = status
    p.controller.set_views(p.controls, p.overlay)
    assert p.controls.statuses[-1] == status
    assert p.capture.start_calls == 0           # attaching views never starts capture


# ------------------------------------------------------- start / stop

def test_start_resets_the_analyser_then_starts_capture(parts):
    parts.controller.start()
    assert parts.capture.start_calls == 1
    assert callable(parts.capture.on_samples) and callable(parts.capture.on_error)
    assert "analyser.reset" in parts.log
    assert parts.log.index("analyser.reset") < parts.log.index("capture.start")
    assert parts.model.capture_status == "active"
    assert parts.controls.statuses[-1] == "active"


@pytest.mark.parametrize("presses", [2, 100])
def test_ca07_pressing_start_repeatedly_opens_only_one_session(parts, presses):
    for _ in range(presses):
        parts.controller.start()
    assert parts.capture.start_calls == 1
    assert parts.model.capture_status == "active"


def test_ca03_stop_stops_capture_and_resets_the_analyser(parts):
    parts.controller.start()
    parts.log.clear()
    parts.controller.stop()
    assert parts.capture.stop_calls == 1
    assert "analyser.reset" in parts.log
    assert parts.model.capture_status == "stopped"
    assert parts.controls.statuses[-1] == "stopped"


def test_stop_when_not_capturing_is_harmless(parts):
    parts.controller.stop()
    assert parts.model.capture_status == "stopped"
    assert parts.controls.statuses[-1] == "stopped"


def test_ca05_start_stop_start_cycle_ten_times(parts):
    for _ in range(10):
        parts.controller.start()
        assert parts.model.capture_status == "active"
        parts.controller.stop()
        assert parts.model.capture_status == "stopped"
    assert parts.capture.start_calls == 10 and parts.capture.stop_calls == 10
    order = [e for e in parts.log if e in ("capture.start", "capture.stop")]
    assert order == ["capture.start", "capture.stop"] * 10
    parts.controller.start()                    # and it still works afterwards
    assert parts.model.capture_status == "active"


# --------------------------------------------------------- errors (CA-06)

def test_ca06_capture_failing_at_start_ends_in_the_error_state(parts):
    parts.capture.fail_with = "no output device"
    parts.controller.start()
    assert parts.model.capture_status == "error"        # not overwritten with "active"
    assert parts.controls.statuses[-1] == "error"
    assert parts.controls.errors == ["no output device"]
    assert parts.capture.stop_calls >= 1
    after_start = parts.log[parts.log.index("capture.start") + 1:]
    assert "analyser.reset" in after_start


def test_ca06_error_while_capturing_then_restart(parts):
    parts.controller.start()
    parts.capture.on_error("device removed")            # the callback given to capture
    assert parts.model.capture_status == "error"
    assert parts.controls.statuses[-1] == "error"
    assert parts.controls.errors == ["device removed"]
    parts.controller.start()                            # CA-05: restart after an error
    assert parts.capture.start_calls == 2
    assert parts.model.capture_status == "active"
    assert parts.controls.statuses[-1] == "active"


# ------------------------------------------------------------- on_samples

def test_samples_go_to_the_analyser_and_each_spectrum_is_mapped_in_order(parts):
    parts.controller.start()
    parts.analyser.script = [[SPECTRUM_1, SPECTRUM_2]]
    parts.capture.on_samples(SAMPLES, RATE)             # via the callback given to capture
    assert parts.analyser.calls == [(SAMPLES, RATE)]
    assert parts.mapper.calls == [SPECTRUM_1, SPECTRUM_2]


def test_d01_model_and_overlay_get_the_latest_colour(parts):
    parts.controller.start()
    parts.analyser.script = [[SPECTRUM_1, SPECTRUM_2]]
    parts.capture.on_samples(SAMPLES, RATE)
    assert parts.model.output_colour == (2, 0, 0)       # the second spectrum wins
    assert parts.overlay.colour == (2, 0, 0)


def test_d01_a_later_batch_replaces_an_earlier_colour(parts):
    parts.controller.start()
    parts.analyser.script = [[SPECTRUM_2], [SPECTRUM_1]]
    parts.capture.on_samples(SAMPLES, RATE)
    parts.capture.on_samples(SAMPLES, RATE)
    assert parts.model.output_colour == (1, 0, 0)
    assert parts.overlay.colour == (1, 0, 0)


def test_no_completed_window_leaves_the_colour_unchanged(parts):
    parts.controller.start()
    parts.analyser.script = [[SPECTRUM_2], []]
    parts.capture.on_samples(SAMPLES, RATE)
    colour_calls_before = parts.mapper.calls[:]
    parts.capture.on_samples(SAMPLES, RATE)             # analyser returns no spectrum
    assert parts.mapper.calls == colour_calls_before
    assert parts.model.output_colour == (2, 0, 0)
    assert parts.overlay.colour == (2, 0, 0)


# ------------------------------------------------------- overlay (D-03/D-04)

def test_d03_overlay_stays_visible_while_enabled(parts):
    parts.controller.start()
    parts.controller.set_overlay_enabled(True)
    parts.analyser.script = [[SPECTRUM_1], [SPECTRUM_2]]
    parts.capture.on_samples(SAMPLES, RATE)
    parts.capture.on_samples(SAMPLES, RATE)
    assert parts.overlay.visible is True
    assert parts.overlay.colour == (2, 0, 0)


def test_d04_disabled_overlay_stays_hidden_and_shows_the_latest_colour_when_enabled_again(parts):
    parts.controller.start()
    parts.controller.set_overlay_enabled(True)
    parts.controller.set_overlay_enabled(False)
    assert parts.overlay.visible is False
    parts.analyser.script = [[SPECTRUM_1]]
    parts.capture.on_samples(SAMPLES, RATE)             # a new colour arrives while hidden
    assert parts.overlay.visible is False               # it must not pop the overlay open
    assert parts.model.output_colour == (1, 0, 0)
    parts.controller.set_overlay_enabled(True)
    assert parts.overlay.visible is True
    assert parts.overlay.colour == (1, 0, 0)            # not a stale colour


# ----------------------------------------------------------- close (CA-08, D-05)

def test_close_stops_capture_and_closes_both_views(parts):
    parts.controller.start()
    parts.controller.set_overlay_enabled(True)
    parts.log.clear()
    parts.controller.close()
    assert parts.capture.stop_calls >= 1
    assert "analyser.reset" in parts.log
    assert parts.model.capture_status == "stopped"
    assert parts.controls.closed is True
    assert parts.overlay.closed is True


def test_close_without_capture_running_is_safe(parts):
    parts.controller.close()
    assert parts.model.capture_status == "stopped"
    assert parts.controls.closed is True and parts.overlay.closed is True
