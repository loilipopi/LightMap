from array import array
from threading import Event, Thread, current_thread
from typing import Callable

POLL_SECONDS = 0.01
SAMPLE_SCALE = 32768.0


def _downmix_pcm16(data: bytes, channels: int) -> list[float]:
    """Average the interleaved native PCM channels and normalize to full scale."""
    pcm = array("h", data)
    if channels == 1:
        return [sample / SAMPLE_SCALE for sample in pcm]
    scale = SAMPLE_SCALE * channels
    return [
        sum(pcm[i:i + channels]) / scale
        for i in range(0, len(pcm), channels)
    ]


class WasapiLoopback:
    """Own the Windows shared-mode playback stream on one worker thread."""

    def __init__(self, block_size: int) -> None:
        self._block_size = block_size
        self._stop = Event()
        self._worker: Thread | None = None

    def open(
        self,
        on_chunk: Callable[[list[float], int], None],
        on_failure: Callable[[str], None],
    ) -> None:
        """Wait until the default output's loopback stream has opened."""
        ready = Event()
        startup_errors: list[Exception] = []
        self._worker = Thread(
            target=self._record,
            args=(on_chunk, on_failure, ready, startup_errors),
            name="LightMap audio",
        )
        self._worker.start()
        ready.wait()
        if startup_errors:
            raise RuntimeError(f"Could not open default playback capture: {startup_errors[0]}")

    def close(self) -> None:
        """Signal stop and wait until the audio worker has freed the device."""
        self._stop.set()
        worker = self._worker
        if worker is not None and worker is not current_thread():
            worker.join()

    def _record(
        self,
        on_chunk: Callable[[list[float], int], None],
        on_failure: Callable[[str], None],
        ready: Event,
        startup_errors: list[Exception],
    ) -> None:
        try:
            import pyaudiowpatch as pyaudio

            with pyaudio.PyAudio() as audio:
                device = audio.get_default_wasapi_loopback()
                channels = int(device["maxInputChannels"])
                sample_rate = int(device["defaultSampleRate"])
                with audio.open(
                    format=pyaudio.paInt16,
                    channels=channels,
                    rate=sample_rate,
                    input=True,
                    input_device_index=device["index"],
                    frames_per_buffer=self._block_size,
                ) as stream:
                    ready.set()
                    while not self._stop.is_set():
                        if not stream.is_active():
                            raise RuntimeError("The playback device stopped responding")
                        available = stream.get_read_available()
                        if available < 0:
                            raise RuntimeError("The playback device is no longer available")
                        if available:
                            data = stream.read(min(available, self._block_size))
                            on_chunk(_downmix_pcm16(data, channels), sample_rate)
                        else:
                            # Waiting on the stop event also lets a silent device close promptly.
                            self._stop.wait(POLL_SECONDS)
        except Exception as exc:
            if not ready.is_set():
                startup_errors.append(exc)
            elif not self._stop.is_set():
                on_failure(f"Playback capture failed: {exc}")
        finally:
            ready.set()
