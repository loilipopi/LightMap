

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
        """
        raise NotImplementedError

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
        """
        raise NotImplementedError

    def reset(self) -> None:
        """
        Preconditions:
            None.
        Postconditions:
            Clears buffered samples and the stored sample rate.
            Window and hop sizes remain unchanged.
        """
        raise NotImplementedError
