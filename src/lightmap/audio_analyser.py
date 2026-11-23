import math


class FrequencyAnalyser:

    def __init__(self, window_size: int = 1024, hop_size: int = 1024) -> None:
        """
        Preconditions:
            0 < hop_size <= window_size.
        Postconditions:
            Window and hop sizes are set to the supplied values
            (system specification: N = 1024, hop_size = N for
            non-overlapping chunks of duration t = N / fs).
            No samples or sample rate are stored.
        Raises:
            ValueError if window_size <= 0, hop_size <= 0, or
            hop_size > window_size.
        """
        if window_size <= 0 or hop_size <= 0 or hop_size > window_size:
            raise ValueError(
                "window_size and hop_size must satisfy 0 < hop_size <= window_size"
            )

        self._window_size: int = window_size
        self._hop_size: int = hop_size
        self._window: tuple[float, ...] = self._periodic_hann_window(window_size)
        self._is_power_of_two: bool = (window_size & (window_size - 1)) == 0
        self._bit_reversal: tuple[int, ...] = (
            self._build_bit_reversal(window_size) if self._is_power_of_two else ()
        )
        self._stage_twiddles: tuple[tuple[complex, ...], ...] = (
            self._build_stage_twiddles(window_size) if self._is_power_of_two else ()
        )
        self._buffer: list[float] = []
        self._sample_rate: int | None = None
        self._frequencies: tuple[float, ...] | None = None

    def analyse(
        self, samples: list[float], sample_rate: int
    ) -> list[list[tuple[float, float]]]:
        """
        Preconditions:
            samples contains finite, single-channel audio values
            immediately following the previously supplied samples.
            sample_rate > 0 and is unchanged between reset calls.
        Postconditions:
            Returns one spectrum per completed N-sample window, in
            chronological order, following the FFT requirements:
              - Applies the periodic Hann window
                w[n] = 0.5 * (1 - cos(2*pi*n / N)) for n = 0 .. N - 1
                before computing the N-point FFT.
              - Each spectrum contains (frequency_hz, magnitude) pairs
                for bins k = 0 through floor(N / 2), where
                frequency_hz = k * sample_rate / N and
                magnitude = sqrt(real^2 + imaginary^2) / N.
            Returns an empty list if no window is complete.
            Retains samples needed for subsequent windows.
            Stores the sample rate. Does not modify samples.
        Raises:
            ValueError if sample_rate <= 0, sample_rate changes without
            reset, or samples contains non-finite values.
        """
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if self._sample_rate is None:
            self._sample_rate = sample_rate
            n = self._window_size
            self._frequencies = tuple(
                k * sample_rate / n for k in range(n // 2 + 1)
            )
        elif self._sample_rate != sample_rate:
            raise ValueError(
                f"sample_rate changed from {self._sample_rate} to {sample_rate} without reset()"
            )

        validated: list[float] = []
        for s in samples:
            val = float(s)
            if not math.isfinite(val):
                raise ValueError("samples must contain only finite values")
            validated.append(val)

        self._buffer.extend(validated)

        n = self._window_size
        if len(self._buffer) < n:
            return []

        assert self._frequencies is not None
        results: list[list[tuple[float, float]]] = []
        start = 0
        limit = len(self._buffer) - n
        while start <= limit:
            frame = self._buffer[start : start + n]
            bins = self._compute_rfft_bins(frame)
            spectrum = [
                (freq, self._compute_magnitude(b.real, b.imag, n))
                for freq, b in zip(self._frequencies, bins)
            ]
            results.append(spectrum)
            start += self._hop_size

        del self._buffer[:start]
        return results

    def reset(self) -> None:
        """
        Preconditions:
            None.
        Postconditions:
            Clears buffered samples and the stored sample rate.
            Window and hop sizes remain unchanged.
        """
        self._buffer.clear()
        self._sample_rate = None
        self._frequencies = None

    @staticmethod
    def _periodic_hann_window(n: int) -> tuple[float, ...]:
        """Return the periodic Hann window: 0.5 * (1 - cos(2*pi*i / n))."""
        two_pi_over_n = 2.0 * math.pi / n
        return tuple(0.5 * (1.0 - math.cos(two_pi_over_n * i)) for i in range(n))

    @staticmethod
    def _compute_magnitude(real: float, imaginary: float, n: int) -> float:
        """Return sqrt(real^2 + imaginary^2) / n for an unnormalized FFT bin."""
        if n <= 0:
            raise ValueError("n must be positive")
        return math.hypot(real, imaginary) / n

    @staticmethod
    def _build_bit_reversal(n: int) -> tuple[int, ...]:
        bits = n.bit_length() - 1
        if bits == 0:
            return (0,)
        rev = [0] * n
        for i in range(n):
            rev[i] = (rev[i >> 1] >> 1) | ((i & 1) << (bits - 1))
        return tuple(rev)

    @staticmethod
    def _build_stage_twiddles(n: int) -> tuple[tuple[complex, ...], ...]:
        stages: list[tuple[complex, ...]] = []
        size = 2
        while size <= n:
            half = size // 2
            step = -2.0 * math.pi / size
            stages.append(
                tuple(
                    complex(math.cos(step * j), math.sin(step * j))
                    for j in range(half)
                )
            )
            size <<= 1
        return tuple(stages)

    def _compute_rfft_bins(self, frame: list[float]) -> list[complex]:
        """Apply the periodic Hann window and compute unnormalized FFT bins 0..floor(N/2)."""
        n = self._window_size
        num_bins = n // 2 + 1
        window = self._window

        if self._is_power_of_two:
            data = [
                complex(frame[idx] * window[idx]) for idx in self._bit_reversal
            ]
            size = 2
            for twiddles in self._stage_twiddles:
                half = size >> 1
                for start in range(0, n, size):
                    for j in range(half):
                        u = data[start + j]
                        t = twiddles[j] * data[start + j + half]
                        data[start + j] = u + t
                        data[start + j + half] = u - t
                size <<= 1
            return data[:num_bins]

        windowed = [s * w for s, w in zip(frame, window)]
        two_pi_over_n = -2.0 * math.pi / n
        bins: list[complex] = []
        for k in range(num_bins):
            real_sum = 0.0
            imag_sum = 0.0
            step = two_pi_over_n * k
            for m, val in enumerate(windowed):
                angle = step * m
                real_sum += val * math.cos(angle)
                imag_sum += val * math.sin(angle)
            bins.append(complex(real_sum, imag_sum))
        return bins
