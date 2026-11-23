"""FrequencyAnalyser tests (owner: Joe).

Requirements covered: FFT-01 .. FFT-05.

Confirmed specification:
  * Window size N = 1024 and chunk duration t = N / fs (no overlap,
    so default hop_size == window_size == 1024).
  * Hann window form: periodic, w[n] = 0.5 * (1 - cos(2*pi*n / N)).
  * Output bins: k = 0 .. floor(N / 2), frequency = k * fs / N Hz,
    magnitude = sqrt(real^2 + imaginary^2) / N.
"""

import math

import numpy as np
import pytest

from lightmap.audio_analyser import FrequencyAnalyser

DEFAULT_WINDOW_SIZE = 1024
FS = 48000
ATOL_ANALYTIC = 1e-6
ATOL_REFERENCE = 1e-6


# ---------------------------------------------------------------- helpers

def hann(n):
    """Periodic Hann window: w[n] = 0.5 * (1 - cos(2*pi*n / N))."""
    return 0.5 * (1.0 - np.cos(2 * np.pi * np.arange(n) / n))


def reference_spectrum(frame, fs):
    """What FFT-02 .. FFT-05 say one analysis result must be."""
    n = len(frame)
    bins = np.fft.rfft(np.asarray(frame, dtype=float) * hann(n))
    mags = np.abs(bins) / n
    return [(k * fs / n, float(m)) for k, m in enumerate(mags)]


def assert_spectrum_matches(actual, expected, atol=ATOL_REFERENCE):
    assert len(actual) == len(expected)
    for (f_got, m_got), (f_want, m_want) in zip(actual, expected):
        assert f_got == pytest.approx(f_want, rel=1e-9, abs=1e-9)
        assert m_got == pytest.approx(m_want, abs=atol)


def magnitudes(spectrum):
    return [m for _, m in spectrum]


def analyser(n=DEFAULT_WINDOW_SIZE, hop=None):
    return FrequencyAnalyser(window_size=n, hop_size=n if hop is None else hop)


def tone(freq, n, fs, amp=1.0):
    t = np.arange(n) / fs
    return (amp * np.sin(2 * np.pi * freq * t)).tolist()


def feed_in_pieces(an, samples, sizes, fs=FS):
    """Feed `samples` in pieces whose sizes cycle through `sizes`;
    return every spectrum produced, in order."""
    out = []
    pos = 0
    i = 0
    while pos < len(samples):
        size = sizes[i % len(sizes)]
        out.extend(an.analyse(samples[pos:pos + size], fs))
        pos += size
        i += 1
    return out


def random_signal(count, seed=0):
    return np.random.default_rng(seed).uniform(-1, 1, count).tolist()


def peak_bin(spectrum, low=0.0, high=float("inf")):
    """Return (frequency_hz, magnitude) of the strongest bin in [low, high]."""
    in_range = [(f, m) for f, m in spectrum if low <= f <= high]
    assert in_range, f"no bins in range [{low}, {high}]"
    return max(in_range, key=lambda pair: pair[1])


# ------------------------------------------------- FFT-01: analysis windows

def test_fft01_default_window_and_hop_size_are_1024():
    an = FrequencyAnalyser()
    signal = random_signal(2 * DEFAULT_WINDOW_SIZE, seed=10)
    assert an.analyse(signal[:DEFAULT_WINDOW_SIZE - 1], FS) == []
    first = an.analyse(signal[DEFAULT_WINDOW_SIZE - 1:DEFAULT_WINDOW_SIZE], FS)
    assert len(first) == 1
    assert_spectrum_matches(first[0], reference_spectrum(signal[:DEFAULT_WINDOW_SIZE], FS))
    second = an.analyse(signal[DEFAULT_WINDOW_SIZE:], FS)
    assert len(second) == 1
    assert_spectrum_matches(second[0], reference_spectrum(signal[DEFAULT_WINDOW_SIZE:], FS))


def test_fft01_no_result_until_a_window_is_complete():
    n = 8
    an = analyser(n)
    assert an.analyse(random_signal(n - 1), FS) == []
    assert len(an.analyse([0.25], FS)) == 1


def test_fft01_empty_input_returns_empty_and_preserves_buffer():
    n = 8
    signal = random_signal(n, seed=11)
    an = analyser(n)
    assert an.analyse([], FS) == []
    assert an.analyse(signal[:n - 1], FS) == []
    assert an.analyse([], FS) == []
    result = an.analyse(signal[n - 1:], FS)
    assert len(result) == 1
    assert_spectrum_matches(result[0], reference_spectrum(signal, FS))


def test_fft01_windows_are_consecutive_and_leftover_samples_are_kept():
    n = 16
    signal = random_signal(10 * n + (n - 1))          # 10 windows + 15 left over
    an = analyser(n)
    spectra = feed_in_pieces(an, signal, sizes=[1, 7, 33, 2, 50, 3, 29])
    assert len(spectra) == 10
    for i, spectrum in enumerate(spectra):
        assert_spectrum_matches(spectrum, reference_spectrum(signal[i * n:(i + 1) * n], FS))

    # one more sample completes an 11th window that reuses the leftovers
    last_sample = 0.5
    more = an.analyse([last_sample], FS)
    assert len(more) == 1
    assert_spectrum_matches(more[0], reference_spectrum(signal[10 * n:] + [last_sample], FS))


def test_fft01_sustained_stream_of_1024_sample_chunks():
    """Simulate AudioCapture delivering 50 consecutive chunks of N = 1024 samples."""
    n = DEFAULT_WINDOW_SIZE
    num_chunks = 50
    signal = random_signal(num_chunks * n, seed=12)
    an = FrequencyAnalyser()
    for i in range(num_chunks):
        chunk = signal[i * n:(i + 1) * n]
        spectra = an.analyse(chunk, FS)
        assert len(spectra) == 1
        assert_spectrum_matches(spectra[0], reference_spectrum(chunk, FS))


def test_fft01_result_does_not_depend_on_how_the_samples_are_chunked():
    n = 64
    signal = random_signal(5000, seed=1)
    all_at_once = analyser(n, hop=32).analyse(signal, FS)
    in_pieces = feed_in_pieces(analyser(n, hop=32), signal, sizes=[1, 31, 100, 7, 333])
    assert len(all_at_once) == len(in_pieces) > 0
    for a, b in zip(all_at_once, in_pieces):
        assert_spectrum_matches(a, b, atol=1e-12)


def test_fft01_overlapping_windows_advance_by_hop_size():
    n, hop = 8, 4
    signal = random_signal(16, seed=2)
    an = analyser(n, hop=hop)
    spectra = an.analyse(signal, FS)
    assert len(spectra) == 3                           # windows start at 0, 4, 8
    for i, spectrum in enumerate(spectra):
        assert_spectrum_matches(spectrum, reference_spectrum(signal[i * hop:i * hop + n], FS))
    more = random_signal(4, seed=3)                    # 4 more samples -> window at 12
    extra = an.analyse(more, FS)
    assert len(extra) == 1
    assert_spectrum_matches(extra[0], reference_spectrum(signal[12:] + more, FS))


def test_fft01_returns_a_list_of_spectra_of_float_pairs():
    result = analyser(8).analyse(random_signal(16), FS)
    assert isinstance(result, list) and len(result) == 2
    for spectrum in result:
        assert isinstance(spectrum, list)
        for pair in spectrum:
            assert isinstance(pair, tuple) and len(pair) == 2
            freq, mag = pair
            assert isinstance(freq, float) and isinstance(mag, float)


def test_fft01_input_samples_are_not_modified():
    signal = random_signal(40)
    original = list(signal)
    analyser(8).analyse(signal, FS)
    assert signal == original


def test_fft01_minimal_window_sizes():
    for n in (1, 2):
        signal = random_signal(n, seed=n + 20)
        spectra = analyser(n).analyse(signal, FS)
        assert len(spectra) == 1
        assert_spectrum_matches(spectra[0], reference_spectrum(signal, FS))


def test_reset_discards_buffered_samples():
    n = 8
    an = analyser(n)
    an.analyse(random_signal(n - 1, seed=4), FS)       # partial window
    an.reset()
    fresh = random_signal(n, seed=5)
    result = an.analyse(fresh, FS)
    assert len(result) == 1                            # not mixed with the old partial window
    assert_spectrum_matches(result[0], reference_spectrum(fresh, FS))


def test_reset_clears_stored_sample_rate_and_preserves_window_and_hop_size():
    n, hop = 8, 4
    an = analyser(n, hop=hop)
    an.analyse(random_signal(n, seed=6), 48000)
    an.reset()
    signal = random_signal(12, seed=7)
    result = an.analyse(signal, 44100)
    assert len(result) == 2                            # hop_size=4 preserved: windows at 0 and 4
    assert len(result[0]) == n // 2 + 1
    assert result[0][1][0] == pytest.approx(44100 / n)
    assert_spectrum_matches(result[1], reference_spectrum(signal[hop:hop + n], 44100))


def test_reset_when_empty_and_repeated_is_safe():
    n = 8
    an = analyser(n)
    an.reset()
    an.reset()
    signal = random_signal(n, seed=13)
    result = an.analyse(signal, FS)
    assert len(result) == 1
    assert_spectrum_matches(result[0], reference_spectrum(signal, FS))


# ----------------------------------------------- FFT-02: Hann window applied

def test_fft02_hann_window_is_applied_all_ones_input():
    """A constant input has a known periodic-Hann windowed spectrum:
    bin 0 = 0.5, bin 1 = 0.25, everything else 0.
    With no window (rectangular) you would get 1.0 at bin 0 and 0 elsewhere,
    so this fails if the Hann window is missing."""
    n = DEFAULT_WINDOW_SIZE
    mags = magnitudes(analyser(n).analyse([1.0] * n, FS)[0])
    assert mags[0] == pytest.approx(0.5, abs=ATOL_ANALYTIC)
    assert mags[1] == pytest.approx(0.25, abs=ATOL_ANALYTIC)
    assert max(mags[2:]) < ATOL_ANALYTIC


def test_fft02_hann_window_is_applied_bin_centred_sine():
    """A sine of amplitude A exactly on bin k gives A/4 at k and A/8 at k+-1."""
    n, k, amp = DEFAULT_WINDOW_SIZE, 100, 0.8
    signal = (amp * np.sin(2 * np.pi * k * np.arange(n) / n)).tolist()
    mags = magnitudes(analyser(n).analyse(signal, FS)[0])
    assert mags[k] == pytest.approx(amp / 4, abs=ATOL_ANALYTIC)
    assert mags[k - 1] == pytest.approx(amp / 8, abs=ATOL_ANALYTIC)
    assert mags[k + 1] == pytest.approx(amp / 8, abs=ATOL_ANALYTIC)
    rest = [m for i, m in enumerate(mags) if i not in (k - 1, k, k + 1)]
    assert max(rest) < ATOL_ANALYTIC


def test_fft02_a_partial_window_is_not_analysed():
    n = DEFAULT_WINDOW_SIZE
    assert analyser(n).analyse([1.0] * (n - 1), FS) == []


# ----------------------------------------------- FFT-03: bins 0 .. floor(N/2)

@pytest.mark.parametrize("n, expected_pairs", [(1, 1), (2, 2), (7, 4), (8, 5), (16, 9), (1024, 513)])
def test_fft03_number_of_bins(n, expected_pairs):
    spectrum = analyser(n).analyse(random_signal(n), FS)[0]
    assert len(spectrum) == expected_pairs == n // 2 + 1


# --------------------------------------------- FFT-04: bin k is k * fs / N Hz

@pytest.mark.parametrize("n, fs", [(1024, 44100), (1024, 48000), (7, 48000), (8, 22050)])
def test_fft04_bin_frequencies(n, fs):
    spectrum = analyser(n).analyse(random_signal(n), fs)[0]
    assert [f for f, _ in spectrum] == pytest.approx([k * fs / n for k in range(n // 2 + 1)])


@pytest.mark.parametrize("fs", [44100, 48000])
@pytest.mark.parametrize("freq", [440.0, 1000.0])
def test_fft04_a_single_tone_peaks_in_the_nearest_bin(freq, fs):
    n = DEFAULT_WINDOW_SIZE
    spectrum = analyser(n).analyse(tone(freq, n, fs), fs)[0]
    peak_freq, peak_mag = peak_bin(spectrum)
    assert peak_mag > 0.0
    assert abs(peak_freq - freq) <= fs / (2 * n) + 1e-9


def test_fft04_two_tones_give_two_peaks_in_the_right_places():
    n, fs = DEFAULT_WINDOW_SIZE, 48000
    mix = [a + b for a, b in zip(tone(440.0, n, fs), tone(1000.0, n, fs))]
    spectrum = analyser(n).analyse(mix, fs)[0]
    half_bin = fs / (2 * n) + 1e-9
    low_freq, low_mag = peak_bin(spectrum, high=700.0)
    high_freq, high_mag = peak_bin(spectrum, low=700.0)
    assert low_mag > 0.0 and high_mag > 0.0
    assert abs(low_freq - 440.0) <= half_bin
    assert abs(high_freq - 1000.0) <= half_bin


def test_fft04_boundary_frequencies_dc_and_nyquist():
    n, fs = DEFAULT_WINDOW_SIZE, 48000
    dc_spectrum = analyser(n).analyse([1.0] * n, fs)[0]
    dc_freq, dc_mag = peak_bin(dc_spectrum)
    assert dc_freq == pytest.approx(0.0)
    assert dc_mag == pytest.approx(0.5, abs=ATOL_ANALYTIC)

    nyquist_signal = [1.0 if i % 2 == 0 else -1.0 for i in range(n)]
    nyq_spectrum = analyser(n).analyse(nyquist_signal, fs)[0]
    nyq_freq, nyq_mag = peak_bin(nyq_spectrum)
    assert nyq_freq == pytest.approx(fs / 2.0)
    assert nyq_mag == pytest.approx(0.5, abs=ATOL_ANALYTIC)


def test_fft04_game_audio_cue_peaks_within_half_bin_width():
    """Simulate game audio: low-level broadband ambience + background music
    harmonics + a prominent objective cue beep (e.g. 2200 Hz)."""
    n, fs = DEFAULT_WINDOW_SIZE, 48000
    cue_freq = 2200.0
    rng = np.random.default_rng(42)
    t = np.arange(n) / fs
    ambience = rng.normal(0.0, 0.08, n)
    music = 0.15 * np.sin(2 * np.pi * 110.0 * t) + 0.12 * np.sin(2 * np.pi * 330.0 * t)
    cue = 0.9 * np.sin(2 * np.pi * cue_freq * t)
    game_audio = (ambience + music + cue).tolist()

    spectrum = analyser(n).analyse(game_audio, fs)[0]
    peak_freq, peak_mag = peak_bin(spectrum)
    assert peak_mag > 0.0
    assert abs(peak_freq - cue_freq) <= fs / (2 * n) + 1e-9


# ------------------------------------- FFT-05: magnitude = sqrt(re^2+im^2)/N

def test_fft05_magnitude_formula_in_isolation():
    """Checklist FFT-05: real = 3, imaginary = 4, N = 10 gives exactly 0.5."""
    assert FrequencyAnalyser._compute_magnitude(3.0, 4.0, 10) == pytest.approx(0.5, abs=1e-12)
    assert FrequencyAnalyser._compute_magnitude(-3.0, -4.0, 10) == pytest.approx(0.5, abs=1e-12)
    assert FrequencyAnalyser._compute_magnitude(0.0, 0.0, 10) == 0.0


@pytest.mark.parametrize("n", [7, 64, 256, 1024])
def test_fft05_matches_a_numpy_reference_on_random_input(n):
    signal = random_signal(3 * n, seed=n)
    spectra = analyser(n).analyse(signal, FS)
    assert len(spectra) == 3
    for i, spectrum in enumerate(spectra):
        assert_spectrum_matches(spectrum, reference_spectrum(signal[i * n:(i + 1) * n], FS))


@pytest.mark.parametrize("n", [7, 64])
def test_fft05_matches_unnormalized_full_fft_without_single_sided_doubling(n):
    signal = random_signal(n, seed=n + 30)
    full_fft = np.fft.fft(np.asarray(signal, dtype=float) * hann(n))
    expected = [(k * FS / n, float(np.abs(full_fft[k]) / n)) for k in range(n // 2 + 1)]
    actual = analyser(n).analyse(signal, FS)[0]
    assert_spectrum_matches(actual, expected)


def test_fft05_silence_gives_zero_finite_magnitudes():
    n = 32
    mags = magnitudes(analyser(n).analyse([0.0] * n, FS)[0])
    assert all(np.isfinite(m) and m == 0.0 for m in mags)


def test_fft05_magnitudes_are_never_negative():
    n = 64
    mags = magnitudes(analyser(n).analyse(random_signal(n, seed=9), FS)[0])
    assert min(mags) >= 0.0


# -------------------------------------------------- precondition validation

@pytest.mark.parametrize("window_size, hop_size", [(0, 1), (-8, 4), (8, 0), (8, -1), (8, 9)])
def test_invalid_window_or_hop_size_raises_value_error(window_size, hop_size):
    with pytest.raises(ValueError):
        FrequencyAnalyser(window_size=window_size, hop_size=hop_size)


@pytest.mark.parametrize("bad_rate", [0, -48000])
def test_non_positive_sample_rate_raises_value_error(bad_rate):
    with pytest.raises(ValueError):
        analyser(8).analyse([0.0] * 8, bad_rate)


def test_changing_sample_rate_without_reset_raises_value_error():
    an = analyser(8)
    an.analyse(random_signal(8, seed=14), 48000)
    with pytest.raises(ValueError):
        an.analyse(random_signal(8, seed=15), 44100)


@pytest.mark.parametrize("bad_sample", [math.nan, math.inf, -math.inf])
def test_non_finite_sample_raises_value_error(bad_sample):
    with pytest.raises(ValueError):
        analyser(8).analyse([0.0, bad_sample, 0.0], FS)
