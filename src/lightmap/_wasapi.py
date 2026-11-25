from array import array
from queue import Empty, SimpleQueue
from threading import Event, Thread, current_thread
from typing import Callable

STATUS_POLL_SECONDS = 0.05
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
        self._chunks: SimpleQueue[bytes | None] = SimpleQueue()
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
        self._chunks.put(None)
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

                def on_audio(in_data: bytes, frame_count: int, time_info, status):
                    if self._stop.is_set():
                        return (None, pyaudio.paComplete)
                    if in_data:
                        self._chunks.put(in_data)
                    return (None, pyaudio.paContinue)

                with audio.open(
                    format=pyaudio.paInt16,
                    channels=channels,
                    rate=sample_rate,
                    input=True,
                    input_device_index=device["index"],
                    frames_per_buffer=self._block_size,
                    stream_callback=on_audio,
                ) as stream:
                    ready.set()
                    while not self._stop.is_set():
                        try:
                            data = self._chunks.get(timeout=STATUS_POLL_SECONDS)
                        except Empty:
                            if not stream.is_active():
                                raise RuntimeError("The playback device stopped responding")
                            continue
                        if data is None:
                            break
                        on_chunk(_downmix_pcm16(data, channels), sample_rate)
        except Exception as exc:
            if not ready.is_set():
                startup_errors.append(exc)
            elif not self._stop.is_set():
                on_failure(f"Playback capture failed: {exc}")
        finally:
            ready.set()
