import math
from typing import Literal

WindowKind = Literal["hann", "low_latency"]


class FrequencyAnalyser:

    def __init__(
        self,
        window_size: int = 1024,
        hop_size: int = 1024,
        *,
        window: WindowKind = "hann",
    ) -> None:
        """
        Preconditions:
            0 < hop_size <= window_size.
            window is "hann" or "low_latency".
        Postconditions:
            Window and hop sizes are set to the supplied values
            (system specification: N = 1024, hop_size = N for
            non-overlapping chunks of duration t = N / fs).
            No samples or sample rate are stored.
        Raises:
            ValueError if window_size <= 0, hop_size <= 0,
            hop_size > window_size, or window is unknown.
        """
        if window_size <= 0 or hop_size <= 0 or hop_size > window_size:
            raise ValueError(
                "window_size and hop_size must satisfy 0 < hop_size <= window_size"
            )
        if window not in ("hann", "low_latency"):
            raise ValueError("window must be 'hann' or 'low_latency'")

        self._window_size: int = window_size
        self._hop_size: int = hop_size
        self._window: tuple[float, ...] = (
            self._periodic_hann_window(window_size)
            if window == "hann"
            else self._low_latency_hann_window(window_size)
        )
        self._is_power_of_two: bool = (window_size & (window_size - 1)) == 0
        if self._is_power_of_two and window_size >= 2:
            half_n = window_size // 2
            self._rfft_bit_reversal: tuple[int, ...] = self._build_bit_reversal(half_n)
            self._rfft_stages: tuple[tuple[int, int, tuple[complex, ...]], ...] = (
                self._build_stage_twiddles(half_n)
            )
            self._rfft_unpack: tuple[complex, ...] = tuple(
                complex(math.cos(-2.0 * math.pi * k / window_size), math.sin(-2.0 * math.pi * k / window_size))
                for k in range(half_n // 2 + 1)
            )
        else:
            self._rfft_bit_reversal = ()
            self._rfft_stages = ()
            self._rfft_unpack = ()
        self._buffer: list[float] = []
        self._sample_rate: int | None = None
        self._frequencies: tuple[float, ...] | None = None

    @property
    def window_size(self) -> int:
        """Return the FFT analysis window size in samples."""
        return self._window_size

    @property
    def hop_size(self) -> int:
        """Return the step size between consecutive windows in samples."""
        return self._hop_size

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
              - Applies the configured analysis window (periodic Hann by
                default: w[n] = 0.5 * (1 - cos(2*pi*n / N))) before
                computing the N-point FFT.
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
        frequencies = self._frequencies
        inv_n = 1.0 / n
        results: list[list[tuple[float, float]]] = []
        start = 0
        limit = len(self._buffer) - n
        while start <= limit:
            frame = self._buffer[start : start + n]
            bins = self._compute_rfft_bins(frame)
            results.append([
                (freq, abs(b) * inv_n)
                for freq, b in zip(frequencies, bins)
            ])
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
    def _low_latency_hann_window(n: int) -> tuple[float, ...]:
        """Return a right-weighted asymmetric Hann window with matching DC gain.

        Places the peak near the newest samples (~9% from the right edge) to
        cut group delay while keeping the full N-sample history for frequency
        resolution and matching the periodic Hann window's coherent gain (n/2).
        """
        if n <= 2:
            return FrequencyAnalyser._periodic_hann_window(n)
        right_len = max(1, min(n // 2, (n * 3) // 32))
        left_len = n - right_len
        raw = [
            0.5 * (1.0 - math.cos(math.pi * i / left_len))
            for i in range(left_len)
        ] + [
            0.5 * (1.0 + math.cos(math.pi * j / right_len))
            for j in range(right_len)
        ]
        scale = (0.5 * n) / sum(raw)
        return tuple(v * scale for v in raw)

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
    def _build_stage_twiddles(n: int) -> tuple[tuple[int, int, tuple[complex, ...]], ...]:
        stages: list[tuple[int, int, tuple[complex, ...]]] = []
        size = 2
        while size <= n:
            half = size // 2
            step = -2.0 * math.pi / size
            stages.append((
                size,
                half,
                tuple(
                    complex(math.cos(step * j), math.sin(step * j))
                    for j in range(half)
                ),
            ))
            size <<= 1
        return tuple(stages)

    def _compute_rfft_bins(self, frame: list[float]) -> list[complex]:
        """Apply the analysis window and compute unnormalized FFT bins 0..floor(N/2)."""
        n = self._window_size
        window = self._window

        if self._is_power_of_two:
            if n == 1:
                return [complex(frame[0] * window[0])]
            # Pack N real windowed samples into an N/2-point complex FFT.
            m = n >> 1
            data = [
                complex(frame[idx << 1] * window[idx << 1], frame[(idx << 1) | 1] * window[(idx << 1) | 1])
                for idx in self._rfft_bit_reversal
            ]
            for size, half, twiddles in self._rfft_stages:
                for start in range(0, m, size):
                    for j in range(half):
                        u = data[start + j]
                        t = twiddles[j] * data[start + j + half]
                        data[start + j] = u + t
                        data[start + j + half] = u - t

            out = [0j] * (m + 1)
            z0 = data[0]
            out[0] = complex(z0.real + z0.imag, 0.0)
            out[m] = complex(z0.real - z0.imag, 0.0)
            half_m = m >> 1
            unpack = self._rfft_unpack
            for k in range(1, half_m):
                zk = data[k]
                zmk_conj = data[m - k].conjugate()
                even = 0.5 * (zk + zmk_conj)
                odd = -0.5j * (zk - zmk_conj) * unpack[k]
                out[k] = even + odd
                out[m - k] = (even - odd).conjugate()
            if half_m > 0:
                out[half_m] = data[half_m].conjugate()
            return out

        num_bins = n // 2 + 1
        windowed = [s * w for s, w in zip(frame, window)]
        two_pi_over_n = -2.0 * math.pi / n
        bins: list[complex] = []
        for k in range(num_bins):
            real_sum = 0.0
            imag_sum = 0.0
            step = two_pi_over_n * k
            for m_idx, val in enumerate(windowed):
                angle = step * m_idx
                real_sum += val * math.cos(angle)
                imag_sum += val * math.sin(angle)
            bins.append(complex(real_sum, imag_sum))
        return bins
