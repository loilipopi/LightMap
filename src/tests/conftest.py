from types import SimpleNamespace

import pytest

from lightmap.app_controller import AppController
from lightmap.app_model import AppModel


class FakeCapture:
    def __init__(self, log):
        self.log = log
        self.start_calls = 0
        self.stop_calls = 0
        self.fail_with = None
        self.active = False

    def start(self, on_samples, on_error):
        assert not self.active
        self.log.append("capture.start")
        self.start_calls += 1
        self.active = True
        self.on_samples = on_samples

        def report_failure(message):
            if self.on_samples is on_samples:
                self.active = False
            on_error(message)

        self.on_error = report_failure
        if self.fail_with is not None:
            raise RuntimeError(self.fail_with)

    def stop(self):
        self.log.append("capture.stop")
        self.stop_calls += 1
        self.active = False


class FakeAnalyser:
    def __init__(self, log):
        self.log = log
        self.calls = []
        self.script = []

    def reset(self):
        self.log.append("analyser.reset")

    def analyse(self, samples, sample_rate):
        self.calls.append((samples, sample_rate))
        return self.script.pop(0) if self.script else []


class FakeMapper:
    def __init__(self):
        self.calls = []

    def map_colour(self, spectrum):
        self.calls.append(spectrum)
        return (len(spectrum), 0, 0)


class FakeControls:
    def __init__(self):
        self.statuses = []
        self.errors = []
        self.input_levels = []
        self.closed = False

    def set_status(self, status):
        assert not self.closed
        self.statuses.append(status)

    def show_error(self, message):
        assert not self.closed
        self.errors.append(message)

    def set_input_level(self, level):
        self.input_levels.append(level)

    def close(self):
        assert not self.closed
        self.closed = True


class FakeOverlay:
    def __init__(self):
        self.colour = (0, 0, 0)
        self.visible = False
        self.closed = False

    def set_colour(self, colour):
        assert not self.closed
        self.colour = colour

    def show(self):
        assert not self.closed
        self.visible = True

    def hide(self):
        assert not self.closed
        self.visible = False

    def close(self):
        self.hide()
        self.closed = True


@pytest.fixture
def make_parts():
    """Build a controller with real state and no hardware or GUI."""
    def make(attach=True):
        log = []
        model = AppModel()
        capture = FakeCapture(log)
        analyser = FakeAnalyser(log)
        mapper = FakeMapper()
        controls = FakeControls()
        overlay = FakeOverlay()
        controller = AppController(model, capture, analyser, mapper)
        if attach:
            controller.set_views(controls, overlay)
        return SimpleNamespace(
            log=log,
            model=model,
            capture=capture,
            analyser=analyser,
            mapper=mapper,
            controls=controls,
            overlay=overlay,
            controller=controller,
        )

    return make


@pytest.fixture
def parts(make_parts):
    return make_parts()
