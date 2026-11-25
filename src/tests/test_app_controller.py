"""AppController tests (owner: Kevin).

Requirements covered: CA-03, CA-05, CA-06, CA-07, CA-08, D-01, D-03, D-04, D-05.

Uses a real AppModel and the fakes from conftest.py for everything else.
Convention: FakeMapper turns a spectrum with k pairs into the colour (k, 0, 0).
"""

from threading import Thread

import pytest
from PIL import Image

from lightmap import app_controller
from lightmap.audio_analyser import FrequencyAnalyser
from lightmap.colour_mapper import ColourMapper
from lightmap.overlay_layout import PREVIEW_COLOUR
from lightmap.preferences import AudioTuning, SmoothingTimes

SPECTRUM_1 = [(100.0, 1.0)]                    # -> colour (1, 0, 0)
SPECTRUM_2 = [(100.0, 1.0), (200.0, 2.0)]      # -> colour (2, 0, 0)
SAMPLES = [0.0] * 8
RATE = 48000


def test_meter_reads_raw_peak_and_idle_uses_quiet_colour(parts, monkeypatch):
    mapper = ColourMapper([[(7, 14, 21)]], {"sample_rate": RATE})
    controller = app_controller.AppController(parts.model, parts.capture, parts.analyser, mapper)
    controller.set_views(parts.controls, parts.overlay)
    quiet = (32, 64, 96)
    controller.set_audio_tuning(AudioTuning(-40, quiet))
    assert parts.overlay.colour == quiet
    now = 10.0
    monkeypatch.setattr(app_controller, "monotonic", lambda: now)
    controller.start()
    parts.analyser.script = [[[(100.0, 0.002)]], [[(100.0, 0.05)]]]
    parts.capture.on_samples(SAMPLES, RATE)
    assert parts.controls.input_levels[-1] == pytest.approx(-47.96, abs=.01)
    assert parts.overlay.colour == quiet
    parts.capture.on_samples(SAMPLES, RATE)
    assert parts.controls.input_levels[-1] == pytest.approx(-20)
    assert parts.overlay.colour == (7, 14, 21)
    now += 0.1
    controller.refresh_idle()
    assert parts.overlay.colour == (7, 14, 21)
    now += 0.2
    controller.refresh_idle()
    assert parts.controls.input_levels[-1] is None
    assert parts.overlay.colour == quiet
    assert parts.model.capture_status == "active"


def test_preview_restores_live_colour_and_remembered_visibility(parts):
    parts.controller.set_overlay_preview(True)
    assert parts.overlay.visible and parts.overlay.colour == PREVIEW_COLOUR
    assert not parts.model.overlay_enabled
    parts.controller.start()
    parts.analyser.script = [[SPECTRUM_2]]
    parts.capture.on_samples(SAMPLES, RATE)
    assert parts.overlay.colour == PREVIEW_COLOUR and parts.model.output_colour == (2, 0, 0)
    parts.controller.set_overlay_preview(False)
    assert not parts.overlay.visible
    parts.controller.set_overlay_enabled(True)
    assert parts.overlay.visible and parts.overlay.colour == (2, 0, 0)


def test_smoothing_blends_successive_updates_and_can_be_disabled(parts, monkeypatch):
    colours = iter([(0, 0, 0), (255, 60, 120), (255, 60, 120), (255, 60, 120)])
    monkeypatch.setattr(parts.mapper, "map_colour", lambda spectrum: next(colours))
    parts.analyser.script = [[SPECTRUM_1]] * 4
    parts.controller.set_smoothing_enabled(True)
    parts.controller.start()
    parts.capture.on_samples(SAMPLES, RATE)
    assert parts.overlay.colour == (0, 0, 0)
    parts.capture.on_samples(SAMPLES, RATE)
    first_step = parts.overlay.colour
    parts.capture.on_samples(SAMPLES, RATE)
    second_step = parts.overlay.colour
    assert all(0 < first < second < target
               for first, second, target in zip(first_step, second_step, (255, 60, 120)))
    parts.controller.set_smoothing_enabled(False)
    assert parts.overlay.colour == (255, 60, 120)
    parts.capture.on_samples(SAMPLES, RATE)
    assert parts.model.output_colour == parts.overlay.colour == (255, 60, 120)


@pytest.mark.parametrize("fade_in,fade_out", [(0, 200), (180, 0), (0, 0), (100, 300)])
def test_independent_fades_follow_audio_in_each_direction(parts, monkeypatch, fade_in, fade_out):
    bright, quiet = (255, 80, 60), (0, 0, 0)
    monkeypatch.setattr(
        parts.mapper, "map_colour", lambda spectrum: bright if spectrum[0][1] > 0 else quiet
    )
    parts.controller.set_smoothing_times(SmoothingTimes(fade_in, fade_out))
    parts.controller.set_smoothing_enabled(True)
    parts.controller.start()
    parts.analyser.script = [[[(100.0, 0.3)]], [[(100.0, 0.0)]], [[(100.0, 0.0)]]]
    parts.capture.on_samples(SAMPLES, RATE)
    at_peak = parts.overlay.colour
    assert (0 < at_peak[0] < 255) if fade_in else (at_peak == bright)
    parts.capture.on_samples(SAMPLES, RATE)
    on_drop = parts.overlay.colour
    parts.capture.on_samples(SAMPLES, RATE)
    if fade_out:
        assert 0 < parts.overlay.colour[0] < on_drop[0] < at_peak[0]
    else:
        assert parts.overlay.colour == on_drop == quiet


def test_fade_out_continues_without_audio_frames(parts, monkeypatch):
    now = 10.0
    monkeypatch.setattr(app_controller, "monotonic", lambda: now)
    bright = (255, 90, 20)
    quiet = (18, 25, 32)
    mapper = ColourMapper([[bright]], {"sample_rate": RATE})
    controller = app_controller.AppController(parts.model, parts.capture, parts.analyser, mapper)
    controller.set_views(parts.controls, parts.overlay)
    controller.set_audio_tuning(AudioTuning(quiet_colour=quiet))
    controller.set_smoothing_times(SmoothingTimes(0, 200))
    controller.set_smoothing_enabled(True)
    controller.start()
    parts.analyser.script = [[[(100.0, 0.3)]]]
    parts.capture.on_samples(SAMPLES, RATE)
    assert parts.overlay.colour == bright
    now += 0.3
    controller.refresh_idle()
    assert parts.controls.input_levels[-1] is None
    now += 0.2
    controller.refresh_idle()
    assert quiet[0] < parts.overlay.colour[0] < bright[0]
    now += 2
    controller.refresh_idle()
    assert parts.overlay.colour == quiet


@pytest.mark.parametrize("fade_in,fade_out", [(0, 200), (200, 0), (100, 300)])
def test_colour_change_fades_out_old_colour_and_fades_in_new_colour_independently(
    parts, monkeypatch, fade_in, fade_out
):
    red, blue = (255, 0, 0), (0, 0, 255)
    monkeypatch.setattr(
        parts.mapper, "map_colour", lambda spectrum: red if spectrum[0][0] == 100.0 else blue
    )
    parts.controller.set_smoothing_times(SmoothingTimes(0, 0))
    parts.controller.set_smoothing_enabled(True)
    parts.controller.start()
    # Start on pure red, then switch to blue with slight peak jitter.
    parts.analyser.script = [
        [[(100.0, 0.3)]],
        [[(200.0, 0.3)]],
        [[(200.0, 0.25)]],
        *([[[(200.0, 0.28)]]] * 120),
    ]
    parts.capture.on_samples(SAMPLES, RATE)
    assert parts.overlay.colour == red
    parts.controller.set_smoothing_times(SmoothingTimes(fade_in, fade_out))
    parts.capture.on_samples(SAMPLES, RATE)
    first = parts.overlay.colour
    parts.capture.on_samples(SAMPLES, RATE)
    second = parts.overlay.colour
    if fade_out:
        assert 0 < second[0] < first[0] < 255
    else:
        assert first[0] == second[0] == 0
    if fade_in:
        assert 0 < first[2] < second[2] < 255
    else:
        assert first[2] == second[2] == 255
    if fade_in and fade_out and fade_in < fade_out:
        assert first[2] > 255 - first[0]
    for _ in range(120):
        parts.capture.on_samples(SAMPLES, RATE)
    assert parts.overlay.colour == blue


def test_idle_fade_out_blends_into_returning_audio(parts, monkeypatch):
    now = 10.0
    monkeypatch.setattr(app_controller, "monotonic", lambda: now)
    red, blue, quiet = (255, 0, 0), (0, 0, 255), (18, 25, 32)
    monkeypatch.setattr(
        parts.mapper,
        "map_colour",
        lambda spectrum, tuning=None: red if spectrum[0][0] == 100.0 else blue,
    )
    parts.controller.set_audio_tuning(AudioTuning(quiet_colour=quiet))
    parts.controller.set_smoothing_times(SmoothingTimes(0, 200))
    parts.controller.set_smoothing_enabled(True)
    parts.controller.start()
    parts.analyser.script = [[[(100.0, 0.3)]], [[(200.0, 0.3)]]]
    parts.capture.on_samples(SAMPLES, RATE)
    assert parts.overlay.colour == red
    parts.controller.set_smoothing_times(SmoothingTimes(100, 200))
    now += 0.3
    parts.controller.refresh_idle()
    now += 0.2
    parts.controller.refresh_idle()
    mid_fade = parts.overlay.colour
    assert quiet[0] < mid_fade[0] < red[0]
    parts.capture.on_samples(SAMPLES, RATE)
    blended = parts.overlay.colour
    assert 0 < blended[0] < mid_fade[0] and mid_fade[2] < blended[2] < blue[2]


def test_changing_palette_remaps_latest_spectrum_and_rejects_bad_image(parts, tmp_path):
    parts.controller.start()
    parts.analyser.script = [[SPECTRUM_1], [SPECTRUM_2]]
    parts.capture.on_samples(SAMPLES, RATE)
    assert parts.overlay.colour == (1, 0, 0)
    path = tmp_path / "custom.png"
    with Image.new("RGB", (1, 1), (10, 20, 30)) as image:
        image.save(path)
    parts.controller.set_colour_map(path)
    assert parts.overlay.colour == (10, 20, 30)
    path.write_text("invalid image")
    with pytest.raises(ValueError):
        parts.controller.set_colour_map(path)
    parts.capture.on_samples(SAMPLES, RATE)
    assert parts.overlay.colour == (10, 20, 30)


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


def test_capture_can_report_an_error_before_start_returns(parts, monkeypatch):
    start = parts.capture.start

    def start_and_fail(on_samples, on_error):
        start(on_samples, on_error)
        worker = Thread(target=parts.capture.on_error, args=("device error",), daemon=True)
        worker.start()
        worker.join(timeout=2)
        assert not worker.is_alive()

    monkeypatch.setattr(parts.capture, "start", start_and_fail)
    parts.controller.start()

    assert parts.controls.statuses == ["stopped", "error"]
    assert parts.controls.errors == ["device error"]
    assert parts.capture.stop_calls == 1


def test_stop_failure_is_reported_and_cleanup_retried_before_restart(parts, monkeypatch):
    parts.controller.start()
    stop = parts.capture.stop

    def fail_to_stop():
        raise RuntimeError("device busy")

    monkeypatch.setattr(parts.capture, "stop", fail_to_stop)
    parts.controller.stop()
    parts.controller.start()
    assert parts.model.capture_status == "error"
    assert parts.controls.errors == ["device busy", "device busy"]
    assert parts.capture.start_calls == 1

    monkeypatch.setattr(parts.capture, "stop", stop)
    parts.controller.start()
    assert parts.capture.start_calls == 2
    assert parts.capture.stop_calls == 1
    assert parts.model.capture_status == "active"


def test_stop_and_restart_ignore_callbacks_from_old_session(parts):
    parts.controller.start()
    old_samples = parts.capture.on_samples
    old_error = parts.capture.on_error
    parts.controller.stop()
    old_samples(SAMPLES, RATE)
    assert parts.analyser.calls == []

    parts.controller.start()
    old_samples(SAMPLES, RATE)
    old_error("stale error")
    assert parts.analyser.calls == []
    assert parts.controls.errors == []
    assert parts.model.capture_status == "active"
    assert parts.capture.active


@pytest.mark.parametrize("rate", [0, -1, float("nan"), 48000.5, True])
def test_invalid_sample_rate_does_not_reach_analyser(parts, rate):
    parts.controller.start()
    with pytest.raises(ValueError, match="sample_rate"):
        parts.capture.on_samples(SAMPLES, rate)
    assert parts.analyser.calls == []
    assert parts.model.output_colour == (0, 0, 0)


@pytest.mark.parametrize("active", [False, True])
def test_close_releases_capture_once_and_ignores_subsequent_actions(parts, active):
    if active:
        parts.controller.start()
    parts.controller.set_overlay_enabled(True)
    assert parts.model.overlay_enabled
    parts.controller.close()
    parts.controller.close()
    parts.controller.start()
    parts.controller.stop()
    parts.controller.set_overlay_enabled(True)
    if active:
        parts.capture.on_samples(SAMPLES, RATE)
    assert parts.capture.stop_calls == 1
    assert parts.capture.start_calls == int(active)
    assert parts.model.overlay_enabled is False
    assert parts.analyser.calls == []
    assert parts.overlay.visible is False
    assert parts.overlay.closed and parts.controls.closed


def test_close_still_closes_views_if_releasing_capture_fails(parts, monkeypatch):
    stop = parts.capture.stop

    def fail_to_stop():
        raise RuntimeError("release failed")

    monkeypatch.setattr(parts.capture, "stop", fail_to_stop)
    parts.controller.close()

    assert parts.controls.errors == ["release failed"]
    assert parts.model.capture_status == "error"
    assert parts.overlay.closed and parts.controls.closed
    monkeypatch.setattr(parts.capture, "stop", stop)
    parts.controller.close()
    assert parts.model.capture_status == "stopped"
    assert parts.capture.stop_calls == 1


@pytest.mark.parametrize("initial_rate_known", [False, True])
def test_image_mapper_uses_reported_sample_rate_and_real_analyser(
    parts, tmp_path, monkeypatch, initial_rate_known
):
    path = tmp_path / "map.png"
    with Image.new("L", (2, 2), 128) as image:
        image.putpixel((1, 0), 255)
        image.save(path)

    configurations = []

    def configure_mapper(pixels, settings):
        configurations.append((pixels, settings))
        return parts.mapper

    monkeypatch.setattr(app_controller, "ColourMapper", configure_mapper)
    analyser = FrequencyAnalyser()
    settings = {"gain": 2.0}
    if initial_rate_known:
        settings["sample_rate"] = RATE
    controller = app_controller.AppController(
        parts.model,
        parts.capture,
        analyser,
        colour_map_path=path,
        colour_map_settings=settings,
    )
    assert len(configurations) == int(initial_rate_known)
    # The controller uses the decoded pixels even when another rate is used.
    path.unlink()
    spectra = []

    def map_spectrum(spectrum):
        spectra.append(spectrum)
        return (1, 2, 3)

    monkeypatch.setattr(parts.mapper, "map_colour", map_spectrum)
    controller.set_views(parts.controls, parts.overlay)
    for window_count, sample_rate in enumerate((RATE, 44100, 44100)):
        controller.start()
        parts.capture.on_samples([0.0] * 512, sample_rate)
        assert len(spectra) == window_count
        parts.capture.on_samples([0.0] * 512, sample_rate)
        assert len(spectra[-1]) == 513
        assert spectra[-1][-1] == (sample_rate / 2, 0.0)
        controller.stop()

    assert configurations[0][0] == [
        [(128, 128, 128), (255, 255, 255)],
        [(128, 128, 128), (128, 128, 128)],
    ]
    assert [settings["sample_rate"] for _, settings in configurations] == [RATE, 44100]
    assert parts.model.settings == {"sample_rate": 44100, "gain": 2.0}
    assert parts.overlay.colour == (1, 2, 3)


def test_colour_map_path_rejects_missing_or_invalid_images(parts, tmp_path):
    path = tmp_path / "map.png"
    build = app_controller.AppController
    with pytest.raises(FileNotFoundError):
        build(parts.model, parts.capture, parts.analyser, colour_map_path=path)
    path.write_text("not an image")
    with pytest.raises(ValueError, match="cannot read colour map image"):
        build(parts.model, parts.capture, parts.analyser, colour_map_path=path)


def test_constructor_rejects_missing_or_conflicting_mapper_configuration(parts, tmp_path):
    build = app_controller.AppController
    args = (parts.model, parts.capture, parts.analyser)
    with pytest.raises(ValueError, match="configured mapper or a colour map path"):
        build(*args)
    with pytest.raises(ValueError, match="configured mapper or a colour map path"):
        build(*args, parts.mapper, colour_map_path=tmp_path / "map.png")


def test_constructor_rejects_invalid_colour_map_sample_rate(parts, tmp_path):
    with pytest.raises(ValueError, match="sample_rate"):
        app_controller.AppController(
            parts.model,
            parts.capture,
            parts.analyser,
            colour_map_path=tmp_path / "map.png",
            colour_map_settings={"sample_rate": float("inf")},
        )


@pytest.mark.parametrize("bad_max", [0, -0.5, float("nan"), float("inf"), True])
def test_constructor_rejects_invalid_colour_map_max_magnitude(parts, tmp_path, bad_max):
    with pytest.raises(ValueError, match="max_magnitude"):
        app_controller.AppController(
            parts.model,
            parts.capture,
            parts.analyser,
            colour_map_path=tmp_path / "map.png",
            colour_map_settings={"max_magnitude": bad_max},
        )


@pytest.mark.parametrize(
    "key, bad_value",
    [
        ("min_frequency", 0),
        ("min_frequency", -20.0),
        ("min_frequency", float("nan")),
        ("floor_db", 0),
        ("floor_db", 6.0),
        ("floor_db", float("-inf")),
        ("floor_db", True),
    ],
)
def test_constructor_rejects_invalid_colour_map_axis_settings(parts, tmp_path, key, bad_value):
    with pytest.raises(ValueError, match=key):
        app_controller.AppController(
            parts.model,
            parts.capture,
            parts.analyser,
            colour_map_path=tmp_path / "map.png",
            colour_map_settings={key: bad_value},
        )


def test_image_mapper_forwards_max_magnitude_setting(parts, tmp_path, monkeypatch):
    path = tmp_path / "map.png"
    with Image.new("RGB", (2, 2), (10, 20, 30)) as image:
        image.save(path)

    captured_settings = []

    def configure_mapper(pixels, settings):
        captured_settings.append(dict(settings))
        return parts.mapper

    monkeypatch.setattr(app_controller, "ColourMapper", configure_mapper)
    # The real analyser gives 513 bins, which FakeMapper would turn into (513, 0, 0).
    monkeypatch.setattr(parts.mapper, "map_colour", lambda spectrum: (0, 0, 0))
    controller = app_controller.AppController(
        parts.model,
        parts.capture,
        FrequencyAnalyser(),
        colour_map_path=path,
        colour_map_settings={"max_magnitude": 0.5},
    )
    controller.start()
    parts.capture.on_samples([0.0] * 1024, RATE)

    assert captured_settings == [{"max_magnitude": 0.5, "sample_rate": RATE}]
    assert parts.model.settings == {"max_magnitude": 0.5, "sample_rate": RATE}
