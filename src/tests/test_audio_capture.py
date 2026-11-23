"""AudioCapture tests (owner: Robert).

Requirements covered: CA-02, CA-03, CA-05, CA-06 (error path), CA-07, CA-08.
CA-01 and CA-04 need a real audio device and stay manual (verified with
Audacity using Windows WASAPI loopback; see the checklist).

Specification:
  * Chunk duration t = N / fs with window size N = 1024 samples
    (one chunk = one analysis window, no overlap).

IMPORTANT: the AudioCapture stub takes no arguments, so it always talks to the
real audio device, and a test machine has none. To make it testable, these
tests assume AudioCapture accepts an optional `backend`:

    AudioCapture(backend=None)   # None -> use the real default output device

where a backend provides two methods (see FakeBackend below):

    backend.open(on_chunk, on_failure)   # start delivering audio
        on_chunk(samples: list[float], sample_rate: int)
        on_failure(message: str)
    backend.close()                      # release the device

Until AudioCapture accepts `backend`, every test here is skipped (the skip
reason says why). If you prefer a different seam, only the `env` fixture and
FakeBackend need to change.
"""

import math
from types import SimpleNamespace

import pytest

from lightmap.audio_capture import AudioCapture

CHUNK_SIZE = 1024   # N = 1024 samples -> chunk duration t = N / fs


class FakeBackend:
    """Stands in for the real audio device layer."""

    sample_rate = 48000

    def __init__(self):
        self.open_streams = 0
        self._on_chunk = None
        self._on_failure = None

    def open(self, on_chunk, on_failure):
        self.open_streams += 1
        self._on_chunk = on_chunk
        self._on_failure = on_failure

    def close(self):
        self.open_streams = max(0, self.open_streams - 1)

    # --- controls used by the tests (they simulate what the device does)

    def deliver(self, samples):
        """Pretend the device produced these samples. Deliberately still works
        after close(), like a real device finishing a buffer late."""
        if self._on_chunk is not None:
            self._on_chunk(list(samples), self.sample_rate)

    def fail(self, message):
        if self._on_failure is not None:
            self._on_failure(message)


class Sink:
    """Records what AudioCapture reports through its callbacks."""

    def __init__(self):
        self.batches = []   # list of (samples, sample_rate)
        self.errors = []

    def on_samples(self, samples, sample_rate):
        self.batches.append((list(samples), sample_rate))

    def on_error(self, message):
        self.errors.append(message)

    @property
    def flat(self):
        return [s for samples, _ in self.batches for s in samples]


@pytest.fixture
def env():
    backend = FakeBackend()
    try:
        capture = AudioCapture(backend=backend)
    except TypeError:
        pytest.skip(
            "AudioCapture does not accept a `backend` yet, so it cannot be "
            "tested without a real audio device. See the note at the top of "
            "this file."
        )
    return SimpleNamespace(capture=capture, backend=backend)


def start(env, sink=None):
    sink = sink or Sink()
    env.capture.start(on_samples=sink.on_samples, on_error=sink.on_error)
    return sink


RAMP = [float(i) for i in range(4 * CHUNK_SIZE)]


# ------------------------------------------------ CA-02: ordered chunks

def test_ca02_samples_arrive_in_order_without_gaps_or_repeats(env):
    sink = start(env)
    for lo, hi in [(0, 100), (100, 350), (350, 1500), (1500, 3 * CHUNK_SIZE)]:
        env.backend.deliver(RAMP[lo:hi])
    assert sink.flat, "no samples were delivered"
    assert sink.flat == RAMP[:len(sink.flat)]


def test_ca02_sample_rate_is_reported_and_constant(env):
    sink = start(env)
    for lo, hi in [(0, 300), (300, 1500), (1500, 2 * CHUNK_SIZE)]:
        env.backend.deliver(RAMP[lo:hi])
    assert sink.batches, "no chunks were delivered"
    assert {rate for _, rate in sink.batches} == {env.backend.sample_rate}


def test_ca02_samples_are_finite_numbers(env):
    sink = start(env)
    env.backend.deliver(RAMP[:CHUNK_SIZE])
    assert sink.flat, "no samples were delivered"
    assert all(isinstance(s, (int, float)) and math.isfinite(s) for s in sink.flat)


def test_ca02_every_batch_has_constant_chunk_size_n_1024(env):
    """Deliver pieces of uneven sizes; every chunk the callback receives
    must contain exactly t * fs = N = 1024 samples with no gaps or overlaps."""
    sink = start(env)
    total_complete = 3 * CHUNK_SIZE
    pieces = [(0, 100), (100, 250), (250, 1600), (1600, 2100), (2100, total_complete + 100)]
    for lo, hi in pieces:
        env.backend.deliver(RAMP[lo:hi])
    assert len(sink.batches) == 3
    assert all(len(samples) == CHUNK_SIZE for samples, _ in sink.batches)
    assert sink.flat == RAMP[:total_complete]


# ------------------------------------------- CA-03 / CA-08: stop and release

def test_ca03_stop_ends_the_callbacks_and_ca08_releases_the_device(env):
    sink = start(env)
    env.backend.deliver(RAMP[:CHUNK_SIZE])
    received = len(sink.batches)
    assert received >= 1
    assert env.backend.open_streams == 1
    env.capture.stop()
    assert env.backend.open_streams == 0
    env.backend.deliver(RAMP[CHUNK_SIZE:2 * CHUNK_SIZE])  # late buffer after stop returned
    assert len(sink.batches) == received                  # no further callbacks


def test_ca08_stop_without_start_is_safe(env):
    env.capture.stop()
    assert env.backend.open_streams == 0


def test_ca08_stop_twice_is_safe(env):
    start(env)
    env.capture.stop()
    env.capture.stop()
    assert env.backend.open_streams == 0


# ------------------------------------------------------ CA-05: restart

def test_ca05_capture_can_be_restarted_ten_times(env):
    for i in range(10):
        sink = start(env)
        assert env.backend.open_streams == 1
        env.backend.deliver(RAMP[:CHUNK_SIZE])
        assert sink.flat, f"no samples after restart {i}"
        env.capture.stop()
        assert env.backend.open_streams == 0


# ------------------------------------------------ CA-07: one session only

def test_ca07_starting_twice_keeps_the_existing_session(env):
    first = start(env)
    second = start(env)
    assert env.backend.open_streams == 1
    env.backend.deliver(RAMP[:CHUNK_SIZE])
    assert first.flat == RAMP[:len(first.flat)] and first.flat
    assert second.batches == []             # the second start changed nothing


# --------------------------------------------- CA-06: the error path

def test_ca06_a_failure_stops_capture_and_reports_a_message(env):
    sink = start(env)
    env.backend.fail("output device was removed")
    assert len(sink.errors) == 1 and isinstance(sink.errors[0], str) and sink.errors[0]
    assert env.backend.open_streams == 0
    env.backend.deliver(RAMP[:CHUNK_SIZE])
    assert sink.batches == []               # nothing is delivered after the failure


def test_ca06_capture_can_be_restarted_after_a_failure(env):
    start(env)
    env.backend.fail("boom")
    sink = start(env)
    assert env.backend.open_streams == 1
    env.backend.deliver(RAMP[:CHUNK_SIZE])
    assert sink.flat
