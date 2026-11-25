import sys
from dataclasses import dataclass, field
from math import isfinite
from threading import Lock, RLock
from typing import Callable, Protocol

from ._wasapi import WasapiLoopback

CHUNK_SIZE = 1024
SampleCallback = Callable[[list[float], int], None]
ErrorCallback = Callable[[str], None]


class CaptureBackend(Protocol):
    """Open a source of mono samples; close stops it and releases its resources."""

    def open(self, on_chunk: SampleCallback, on_failure: ErrorCallback) -> None: ...

    def close(self) -> None: ...


@dataclass
class _Session:
    backend: CaptureBackend
    on_error: ErrorCallback
    pending: list[float] = field(default_factory=list)
    rate: int | None = None
    error: str | None = None
    opening: bool = True
    stopping: bool = False


class AudioCapture:
    """Capture playback and deliver consecutive mono windows of 1024 samples."""

    def __init__(self, backend: CaptureBackend | None = None) -> None:
        """Use the default Windows playback device unless a source is supplied."""
        self._backend = backend
        self._session: _Session | None = None
        self._commands = Lock()
        self._state = RLock()

    def start(self, on_samples: SampleCallback, on_error: ErrorCallback) -> None:
        """Open one session and report any failure after releasing its source."""
        if not callable(on_samples) or not callable(on_error):
            raise TypeError("capture callbacks must be callable")
        with self._commands:
            with self._state:
                if self._session is not None:
                    return
                backend = self._backend if self._backend is not None else WasapiLoopback(CHUNK_SIZE)
                session = self._session = _Session(backend, on_error)
            try:
                if self._backend is None and sys.platform != "win32":
                    raise RuntimeError("Playback capture requires Windows WASAPI")
                backend.open(
                    lambda samples, rate: self._receive(session, samples, rate, on_samples),
                    lambda message: self._fail(session, message),
                )
            except Exception as exc:
                self._fail(session, str(exc) or type(exc).__name__)
            finally:
                with self._state:
                    session.opening = False
                    startup_failed = session.error is not None
                if startup_failed:
                    self._finish_failure(session)

    def stop(self) -> None:
        """Discard the partial window and stop delivering samples and errors."""
        with self._commands:
            with self._state:
                session = self._session
                if session is None:
                    return
                session.stopping = True
            session.backend.close()
            with self._state:
                self._session = None

    def _receive(
        self, session: _Session, samples: list[float], rate: int, callback: SampleCallback
    ) -> None:
        try:
            with self._state:
                if self._session is not session or session.stopping or session.error is not None:
                    return
                if type(rate) is not int or rate <= 0:
                    raise ValueError("Capture reported an invalid sample rate")
                if session.rate is not None and session.rate != rate:
                    raise ValueError("Playback sample rate changed during capture")
                if not all(isfinite(sample) for sample in samples):
                    raise ValueError("Capture reported non-finite samples")
                session.rate = rate
                session.pending.extend(samples)
                end = len(session.pending) // CHUNK_SIZE * CHUNK_SIZE
                for offset in range(0, end, CHUNK_SIZE):
                    callback(session.pending[offset:offset + CHUNK_SIZE], rate)
                del session.pending[:end]
        except Exception as exc:
            if self._backend is None:
                # The audio worker reports the error after its stream has closed.
                raise
            self._fail(session, str(exc) or type(exc).__name__)

    def _fail(self, session: _Session, message: str) -> None:
        with self._state:
            if self._session is not session or session.stopping or session.error is not None:
                return
            session.error = message or "Audio capture failed"
            if session.opening:
                # A source can report a failure before its open() call returns.
                return
        self._finish_failure(session)

    def _finish_failure(self, session: _Session) -> None:
        message = session.error or "Audio capture failed"
        try:
            session.backend.close()
        except Exception as exc:
            message = f"{message}. Releasing the capture source also failed: {exc}"
        with self._state:
            if self._session is session and not session.stopping:
                self._session = None
                session.on_error(message)
