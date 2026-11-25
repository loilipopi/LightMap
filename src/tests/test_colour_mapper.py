"""ColourMapper tests (owner: Taj).

Requirements covered: CM-01, CM-02, CM-03, D-02.

Confirmed specification:
  * 2D colour map image:
      - Horizontal axis = frequency: logarithmic, min_frequency (default 20 Hz)
        = first (leftmost) column, fs / 2 = last (rightmost) column.
      - Vertical axis = magnitude in decibels relative to max_magnitude
        (default 0.5): linear in dB, floor_db (default -60 dB) = bottom row,
        0 dB = top row.
      - Out-of-range coordinates (including 0 Hz) clamp to the nearest edge.
      - Points between pixel centres use per-channel bilinear interpolation;
        a 1-pixel-tall or 1-pixel-wide map is constant along that axis.
  * Bins below floor_db are excluded from the colour.
  * D-02 averaging formula: power-weighted (magnitude squared) mean RGB of
    the colours that the remaining bins map to. If no bin is at or above the
    floor, the output is black (0, 0, 0).
  * Colour tolerance: +-1 per RGB channel for ColourMapper.

Most hand-computed tests use settings chosen so the axes have round numbers:
  * min_frequency = fs / 32 = 1500 Hz, so fs / 2 is 16x min_frequency and
    1500, 3000, 6000, 12000, 24000 Hz sit at 0, 1/4, 1/2, 3/4, 1 of the width.
  * max_magnitude = 1 and floor_db = -20, so magnitudes 0.1, 10^-0.5 and 1
    sit at the bottom, middle and top rows, and 10^-0.25 sits 3/4 of the
    way up.
"""

import copy
import numbers
from pathlib import Path

import pytest

from lightmap.colour_mapper import ColourMapper
from lightmap.preferences import AudioTuning

FS = 48000.0
NYQUIST = FS / 2.0
CHANNEL_TOLERANCE = 1

# Settings with round-number axes (see the module docstring).
F_MIN = FS / 32                     # 1500 Hz: first column
F_QUARTER = F_MIN * 2               # 3000 Hz: 1/4 of the width
F_MID = F_MIN * 4                   # 6000 Hz: middle column
F_THREE_QUARTER = F_MIN * 8         # 12000 Hz: 3/4 of the width
M_TOP = 1.0                         # 0 dB: top row
M_BOTTOM = 0.1                      # -20 dB: bottom row (the floor)
M_MID = 10 ** -0.5                  # -10 dB: middle row
M_THREE_QUARTER = 10 ** -0.25       # -5 dB: 3/4 of the way up
SETTINGS: dict[str, float] = {
    "sample_rate": FS,
    "min_frequency": F_MIN,
    "max_magnitude": M_TOP,
    "floor_db": -20.0,
}


def test_noise_floor_changes_sensitivity_and_returns_custom_quiet_colour():
    mapper = ColourMapper([[(9, 15, 80)]], {"sample_rate": FS})
    quiet = (30, 60, 90)
    spectrum = [(440.0, 0.002)]  # Approximately -48 dB for the default reference.
    assert mapper.map_colour(spectrum, tuning=AudioTuning(-60, quiet)) == (9, 15, 80)
    assert mapper.map_colour(spectrum, tuning=AudioTuning(-40, quiet)) == quiet
    assert mapper.map_colour([(440.0, 0.0)], tuning=AudioTuning(-100, quiet)) == quiet


def test_frequency_emphasis_weights_power_and_can_mute_entire_bands():
    mapper = ColourMapper([[(255, 0, 0), (0, 0, 255)]], {
        "sample_rate": FS, "min_frequency": 100.0,
    })
    spectrum = [(100.0, 0.05), (NYQUIST, 0.05)]
    quiet = (8, 9, 10)
    # 200% applies +15.1 dB amplitude gain (32x power weight), so ratio is 1:32 -> (8, 0, 247).
    assert mapper.map_colour(spectrum, tuning=AudioTuning(high=200)) == (8, 0, 247)
    assert mapper.map_colour(spectrum, tuning=AudioTuning(high=0)) == (255, 0, 0)
    assert mapper.map_colour(
        spectrum, tuning=AudioTuning(quiet_colour=quiet, low=0, high=0)
    ) == quiet
    tuning = AudioTuning(low=25, mid=50, high=200)
    assert tuning.weight(100) == pytest.approx(0.25 ** 5)
    assert tuning.weight(1000) == pytest.approx(0.5 ** 5)
    assert tuning.weight(10000) == pytest.approx(2.0 ** 5)
    # Smooth crossovers transition monotonically across 250 Hz and 4000 Hz.
    assert tuning.gain(100) < tuning.gain(249) < tuning.gain(250) < tuning.gain(1000)
    assert tuning.gain(1000) < tuning.gain(3999) < tuning.gain(4000) < tuning.gain(10000)


def test_frequency_emphasis_affects_noise_floor_and_vertical_loudness_axis():
    quiet = (12, 24, 36)
    mapper = ColourMapper([[(255, 255, 255)], [(0, 0, 0)]], {"sample_rate": FS})
    # Raw -68 dB is below the -60 dB floor at 100%, but +23.9 dB at 300% lifts it above the floor.
    quiet_high = [(10000.0, 0.0002)]
    assert mapper.map_colour(quiet_high, tuning=AudioTuning(-60, quiet, high=100)) == quiet
    lifted = mapper.map_colour(quiet_high, tuning=AudioTuning(-60, quiet, high=300))
    assert lifted != quiet and lifted[0] > 0
    # Raw -48 dB is above -60 dB at 100%, but -30.1 dB at 25% drops it below the floor.
    quiet_low = [(100.0, 0.002)]
    assert mapper.map_colour(quiet_low, tuning=AudioTuning(-60, quiet, low=100)) != quiet
    assert mapper.map_colour(quiet_low, tuning=AudioTuning(-60, quiet, low=25)) == quiet
    # On a 2D map, boosting a band increases its vertical (dB) brightness and cutting lowers it.
    mid_bin = [(1000.0, 0.015)]
    cut = mapper.map_colour(mid_bin, tuning=AudioTuning(-60, quiet, mid=50))
    neutral = mapper.map_colour(mid_bin, tuning=AudioTuning(-60, quiet, mid=100))
    boosted = mapper.map_colour(mid_bin, tuning=AudioTuning(-60, quiet, mid=200))
    assert cut[0] < neutral[0] < boosted[0]


# ---------------------------------------------------------------- helpers

def make_mapper(colour_map, settings=None):
    return ColourMapper(colour_map, dict(SETTINGS) if settings is None else settings)


def uniform_map(colour=(10, 20, 30), rows=4, cols=5):
    return [[colour] * cols for _ in range(rows)]


def gradient_map(cols=16):
    return [[(c * 16, 255 - c * 16, 7) for c in range(cols)]]


def distinct_map(rows=8, cols=8):
    """Every pixel has its own colour."""
    return [[(r * 30, c * 30, (r + c) * 10) for c in range(cols)] for r in range(rows)]


def corner_2x2_map():
    """2x2 map with four distinct corners:
    top-left = red, top-right = green, bottom-left = blue, bottom-right = yellow.
    """
    return [
        [(255, 0, 0), (0, 255, 0)],
        [(0, 0, 255), (255, 255, 0)],
    ]


# Spectra with at least one bin at or above the floor.
AUDIBLE_SPECTRA = {
    "single-mid": [(1000.0, 0.25)],
    "beyond-range": [(1e9, 1e9)],
    "zero-hz": [(0.0, 0.5)],
    "many-bins": [(f * 100.0, (f % 7) * 0.1) for f in range(60)],
}
SILENT_SPECTRA = {
    "single-zero": [(0.0, 0.0)],
    "all-zero": [(f * 100.0, 0.0) for f in range(513)],
    "all-below-floor": [(1000.0, 0.05), (5000.0, 0.09)],
}
SPECTRA = {**AUDIBLE_SPECTRA, **SILENT_SPECTRA}


def assert_valid_colour(colour):
    assert isinstance(colour, tuple) and len(colour) == 3
    for channel in colour:
        assert isinstance(channel, numbers.Integral)
        assert 0 <= channel <= 255


def assert_colour_close(actual, expected, tolerance=CHANNEL_TOLERANCE):
    assert_valid_colour(actual)
    for got, want in zip(actual, expected):
        assert abs(got - want) <= tolerance, f"{actual} is not within {tolerance} of {expected}"


# ------------------------------------------------------ output is a colour

@pytest.mark.parametrize("name", SPECTRA)
def test_result_is_an_rgb_tuple_of_integers_0_to_255(name):
    assert_valid_colour(make_mapper(gradient_map()).map_colour(SPECTRA[name]))


# ------------------------------------------- D-02: power-weighted mean RGB

@pytest.mark.parametrize("name", AUDIBLE_SPECTRA)
def test_d02_uniform_map_gives_that_colour_for_any_audible_spectrum(name):
    """Independent of the averaging formula: averaging identical colours
    must give that colour."""
    assert make_mapper(uniform_map((10, 20, 30))).map_colour(SPECTRA[name]) == (10, 20, 30)


@pytest.mark.parametrize("name", SILENT_SPECTRA)
def test_d02_silence_gives_black_even_on_a_map_with_no_black(name):
    assert make_mapper(uniform_map((10, 20, 30))).map_colour(SPECTRA[name]) == (0, 0, 0)


@pytest.mark.parametrize("name", AUDIBLE_SPECTRA)
def test_d02_result_stays_inside_the_colour_range_of_the_map(name):
    cmap = distinct_map()
    result = make_mapper(cmap).map_colour(SPECTRA[name])
    for channel in range(3):
        values = [pixel[channel] for row in cmap for pixel in row]
        assert min(values) <= result[channel] <= max(values)


def test_d02_result_is_the_power_weighted_mean_of_the_per_pair_colours():
    mapper = make_mapper(distinct_map())
    spectrum = [
        (0.0, 0.15),
        (500.0, 0.2),
        (5000.0, 0.9),
        (12000.0, 0.4),
        (NYQUIST, 1.0),
    ]
    per_pair = [mapper._colour_for_pair(f, m) for f, m in spectrum]
    total_power = sum(m * m for _, m in spectrum)
    expected = [
        sum(m * m * colour[i] for (_, m), colour in zip(spectrum, per_pair)) / total_power
        for i in range(3)
    ]
    assert_colour_close(mapper.map_colour(spectrum), expected)


@pytest.mark.parametrize("pair", [(5000.0, 0.25), (5000.0, 0.9), (0.0, M_BOTTOM)])
def test_d02_a_single_pair_gives_that_pairs_colour(pair):
    mapper = make_mapper(distinct_map())
    assert mapper.map_colour([pair]) == mapper._colour_for_pair(*pair)


def test_d02_hand_computed_spectra_give_the_expected_power_weighted_average():
    """Hand-computed power-weighted mean RGB over a 1-row 3-pixel custom map
    where min_frequency -> red (255, 0, 0), the middle (6000 Hz) -> green
    (0, 255, 0), and fs/2 -> blue (0, 0, 255)."""
    mapper = make_mapper([[(255, 0, 0), (0, 255, 0), (0, 0, 255)]])

    # Equal magnitudes (1, 1, 1) -> powers 1:1:1 -> (85, 85, 85)
    assert_colour_close(
        mapper.map_colour([(F_MIN, 1.0), (F_MID, 1.0), (NYQUIST, 1.0)]),
        (85.0, 85.0, 85.0),
    )
    # Magnitudes 3:1 between red and blue -> powers 9:1 -> (229.5, 0, 25.5)
    assert_colour_close(
        mapper.map_colour([(F_MIN, 3.0), (NYQUIST, 1.0)]),
        (229.5, 0.0, 25.5),
    )
    # Magnitudes 1:2:5 -> powers 1:4:25 -> R=255/30=8.5, G=1020/30=34, B=6375/30=212.5
    assert_colour_close(
        mapper.map_colour([(F_MIN, 1.0), (F_MID, 2.0), (NYQUIST, 5.0)]),
        (8.5, 34.0, 212.5),
    )
    # Zero-magnitude bin is excluded; the positive bin determines the output
    assert_colour_close(
        mapper.map_colour([(F_MIN, 0.0), (F_MID, 2.5)]),
        (0.0, 255.0, 0.0),
    )


def test_d02_bins_below_the_floor_are_excluded():
    """With floor_db = -20 (magnitude 0.1), a bin at 0.09 is excluded however
    many there are, and a bin exactly at the floor is included."""
    mapper = make_mapper([[(255, 0, 0), (0, 0, 255)]])

    # Hundreds of red bins just under the floor do not dilute one blue bin.
    spectrum = [(F_MIN, 0.09)] * 500 + [(NYQUIST, 0.2)]
    assert mapper.map_colour(spectrum) == (0, 0, 255)

    # A bin exactly at the floor counts.
    assert mapper.map_colour([(F_MIN, M_BOTTOM)]) == (255, 0, 0)


def test_d02_2d_map_uses_magnitude_for_both_vertical_position_and_weight():
    """Hand-computed 2D spectrum on the 2x2 corner map."""
    mapper = make_mapper(corner_2x2_map())

    # (F_MIN, 1.0)     -> top-left (255, 0, 0), power 1.0
    # (fs/2, 10^-0.5)  -> right-edge midpoint (127.5, 255, 0), power 0.1
    # R = (255 + 12.75) / 1.1 = 243.41, G = 25.5 / 1.1 = 23.18, B = 0
    assert_colour_close(
        mapper.map_colour([(F_MIN, M_TOP), (NYQUIST, M_MID)]),
        (243.41, 23.18, 0.0),
    )


# --------------------------------------- CM-01: every bin above the floor counts

@pytest.mark.parametrize("length", [2, 9, 513])
def test_cm01_every_position_in_the_spectrum_changes_the_result(length):
    """Replace one pair of an otherwise identical spectrum with a pair that
    lands on a different colour. The result must change wherever the replaced
    pair sits - including the first (k=0) and last (k=floor(N/2)) bins."""
    mapper = make_mapper(distinct_map())
    low, high = (0.0, M_BOTTOM), (NYQUIST, M_TOP)   # opposite corners of the 2D map
    assert mapper._colour_for_pair(*low) != mapper._colour_for_pair(*high), (
        "test setup: these two pairs must map to different colours"
    )
    baseline = mapper.map_colour([low] * length)
    for k in range(length):
        spectrum = [low] * length
        spectrum[k] = high
        assert mapper.map_colour(spectrum) != baseline, f"bin {k} was ignored"


# ------------------------------------ CM-02: log frequency axis (horizontal)

def test_cm02_two_pixel_black_and_white_map_on_a_log_frequency_axis():
    """Map = one row [black, white]. min_frequency maps to black, fs / 2 to
    white, and each doubling of frequency moves a quarter of the way across
    (fs / 2 is 16x min_frequency)."""
    mapper = make_mapper([[(0, 0, 0), (255, 255, 255)]])

    assert_colour_close(mapper.map_colour([(F_MIN, M_TOP)]), (0.0, 0.0, 0.0))
    assert_colour_close(mapper.map_colour([(F_QUARTER, M_TOP)]), (63.75, 63.75, 63.75))
    assert_colour_close(mapper.map_colour([(F_MID, M_TOP)]), (127.5, 127.5, 127.5))
    assert_colour_close(mapper.map_colour([(F_THREE_QUARTER, M_TOP)]), (191.25, 191.25, 191.25))
    assert_colour_close(mapper.map_colour([(NYQUIST, M_TOP)]), (255.0, 255.0, 255.0))


def test_cm02_frequencies_outside_the_axis_clamp_to_the_edges():
    mapper = make_mapper([[(0, 0, 0), (255, 255, 255)]])

    for low in (0.0, 100.0, F_MIN / 2):
        assert mapper.map_colour([(low, M_TOP)]) == (0, 0, 0)
    for high in (NYQUIST * 1.5, 1e9):
        assert mapper.map_colour([(high, M_TOP)]) == (255, 255, 255)


def test_cm02_default_min_frequency_is_20_hz():
    """20 Hz is the first column, and the geometric mean of 20 Hz and fs / 2
    (about 692.8 Hz) is the middle."""
    mapper = ColourMapper([[(0, 0, 0), (255, 255, 255)]], {"sample_rate": FS})

    assert mapper.map_colour([(20.0, 0.5)]) == (0, 0, 0)
    assert mapper.map_colour([(0.0, 0.5)]) == (0, 0, 0)
    assert_colour_close(
        mapper.map_colour([((20.0 * NYQUIST) ** 0.5, 0.5)]),
        (127.5, 127.5, 127.5),
    )
    assert mapper.map_colour([(NYQUIST, 0.5)]) == (255, 255, 255)


# ----------------------------------------- CM-02: decibel axis (vertical)

def test_cm02_two_pixel_vertical_black_and_white_map_on_a_decibel_axis():
    """Map = one column (top white, bottom black), floor_db = -20. The floor
    gives black, 0 dB gives white, -10 dB the midpoint, and louder magnitudes
    clamp to white. Frequency has no effect on a 1-column map."""
    mapper = make_mapper([[(255, 255, 255)], [(0, 0, 0)]])

    assert_colour_close(mapper.map_colour([(F_MIN, M_BOTTOM)]), (0.0, 0.0, 0.0))
    assert_colour_close(mapper.map_colour([(F_MIN, M_MID)]), (127.5, 127.5, 127.5))
    assert_colour_close(mapper.map_colour([(F_MIN, M_THREE_QUARTER)]), (191.25, 191.25, 191.25))
    assert_colour_close(mapper.map_colour([(F_MIN, M_TOP)]), (255.0, 255.0, 255.0))
    assert_colour_close(mapper.map_colour([(F_MIN, M_TOP * 5)]), (255.0, 255.0, 255.0))
    assert_colour_close(mapper.map_colour([(NYQUIST, M_MID)]), (127.5, 127.5, 127.5))


def test_cm02_default_max_magnitude_and_floor_are_0_5_and_minus_60_db():
    mapper = ColourMapper([[(255, 255, 255)], [(0, 0, 0)]], {"sample_rate": FS})

    assert mapper.map_colour([(1000.0, 0.0005)]) == (0, 0, 0)            # -60 dB: floor
    assert_colour_close(
        mapper.map_colour([(1000.0, 0.5 * 10 ** (-30 / 20))]),           # -30 dB: middle
        (127.5, 127.5, 127.5),
    )
    assert mapper.map_colour([(1000.0, 0.5)]) == (255, 255, 255)         # 0 dB: top
    assert mapper.map_colour([(1000.0, 1.0)]) == (255, 255, 255)         # clamped
    # Below the floor nothing is left, so the output is black (not the bottom row).
    grey = ColourMapper([[(200, 200, 200)]], {"sample_rate": FS})
    assert grey.map_colour([(1000.0, 0.0004)]) == (0, 0, 0)


def test_cm02_custom_max_magnitude_and_floor_rescale_the_vertical_axis():
    mapper = ColourMapper(
        [[(255, 255, 255)], [(0, 0, 0)]],
        {"sample_rate": FS, "max_magnitude": 2.0, "floor_db": -40.0},
    )

    assert mapper.map_colour([(1000.0, 0.02)]) == (0, 0, 0)              # -40 dB re 2.0
    assert_colour_close(mapper.map_colour([(1000.0, 0.2)]), (127.5, 127.5, 127.5))
    assert mapper.map_colour([(1000.0, 2.0)]) == (255, 255, 255)


# ----------------------------------------- CM-02: 2D bilinear lookup

def test_cm02_2x2_map_bilinear_interpolation():
    """2x2 map with distinct corners: corners, centre, asymmetric interior
    point, and out-of-range clamping match bilinear interpolation within +-1."""
    mapper = make_mapper(corner_2x2_map())

    # Exact corners
    assert_colour_close(mapper.map_colour([(F_MIN, M_TOP)]), (255.0, 0.0, 0.0))
    assert_colour_close(mapper.map_colour([(NYQUIST, M_TOP)]), (0.0, 255.0, 0.0))
    assert_colour_close(mapper.map_colour([(F_MIN, M_BOTTOM)]), (0.0, 0.0, 255.0))
    assert_colour_close(mapper.map_colour([(NYQUIST, M_BOTTOM)]), (255.0, 255.0, 0.0))

    # Exact centre -> mean of all four corners
    assert_colour_close(mapper.map_colour([(F_MID, M_MID)]), (127.5, 127.5, 63.75))

    # Asymmetric interior point: u = 0.25 (3000 Hz), v = 0.75 (-5 dB)
    # Weights: TL=0.5625, TR=0.1875, BL=0.1875, BR=0.0625
    assert_colour_close(
        mapper.map_colour([(F_QUARTER, M_THREE_QUARTER)]),
        (159.375, 63.75, 47.8125),
    )

    # Values past both edges clamp to the top-right corner (0, 255, 0)
    assert_colour_close(mapper.map_colour([(1e9, 1e9)]), (0.0, 255.0, 0.0))

    # The lookup itself clamps 0 Hz and magnitude 0 to the bottom-left corner,
    # even though map_colour excludes magnitude 0 as below the floor.
    assert mapper._colour_for_pair(0.0, 0.0) == (0, 0, 255)


def test_cm02_single_pixel_map_is_constant():
    """A 1x1 map returns its single pixel colour for any pair above the floor."""
    mapper = make_mapper([[(42, 128, 200)]])
    for pair in [(0.0, M_BOTTOM), (F_MID, M_MID), (1e9, 1e9)]:
        assert mapper.map_colour([pair]) == (42, 128, 200)


def test_cm02_gradient_and_custom_maps_match_hand_computed_colours():
    """Gradient map and custom map with known pixels; hand-computed expected
    colours along the log frequency axis, within +-1 per RGB channel."""
    # 4-pixel linear gradient: pixel centres at 0, 1/3, 2/3 and 1 of the width,
    # i.e. at F_MIN * 16 ** (0, 1/3, 2/3, 1).
    grad = [[(0, 255, 0), (85, 170, 85), (170, 85, 170), (255, 0, 255)]]
    grad_mapper = make_mapper(grad)
    assert_colour_close(grad_mapper.map_colour([(F_MIN, M_TOP)]), (0.0, 255.0, 0.0))
    assert_colour_close(grad_mapper.map_colour([(F_MIN * 16 ** (1 / 3), M_TOP)]), (85.0, 170.0, 85.0))
    assert_colour_close(grad_mapper.map_colour([(F_MID, M_TOP)]), (127.5, 127.5, 127.5))
    assert_colour_close(grad_mapper.map_colour([(F_MIN * 16 ** (2 / 3), M_TOP)]), (170.0, 85.0, 170.0))
    assert_colour_close(grad_mapper.map_colour([(NYQUIST, M_TOP)]), (255.0, 0.0, 255.0))

    # 3-pixel custom map: red at F_MIN, green at the middle, blue at fs/2
    custom_mapper = make_mapper([[(255, 0, 0), (0, 255, 0), (0, 0, 255)]])
    assert_colour_close(custom_mapper.map_colour([(F_MIN, M_TOP)]), (255.0, 0.0, 0.0))
    assert_colour_close(custom_mapper.map_colour([(F_QUARTER, M_TOP)]), (127.5, 127.5, 0.0))
    assert_colour_close(custom_mapper.map_colour([(F_MID, M_TOP)]), (0.0, 255.0, 0.0))
    assert_colour_close(custom_mapper.map_colour([(F_THREE_QUARTER, M_TOP)]), (0.0, 127.5, 127.5))
    assert_colour_close(custom_mapper.map_colour([(NYQUIST, M_TOP)]), (0.0, 0.0, 255.0))


# ------------------------------------------------- invalid construction

@pytest.mark.parametrize(
    "colour_map",
    [[], [[]], [[(0, 0, 0)], [(0, 0, 0), (1, 1, 1)]]],
    ids=["no-rows", "empty-row", "ragged"],
)
def test_rejects_a_colour_map_that_is_not_a_nonempty_rectangle(colour_map):
    with pytest.raises(ValueError, match="rectangular"):
        ColourMapper(colour_map, dict(SETTINGS))


@pytest.mark.parametrize(
    "changes",
    [
        {"sample_rate": None},
        {"sample_rate": 0.0},
        {"sample_rate": float("inf")},
        {"sample_rate": True},
        {"min_frequency": 0.0},
        {"min_frequency": NYQUIST},
        {"min_frequency": float("nan")},
        {"max_magnitude": 0.0},
        {"max_magnitude": -1.0},
        {"floor_db": 0.0},
        {"floor_db": 10.0},
        {"floor_db": float("-inf")},
    ],
    ids=lambda changes: ",".join(f"{k}={v}" for k, v in changes.items()),
)
def test_rejects_invalid_settings(changes):
    settings = dict(SETTINGS)
    for key, value in changes.items():
        if value is None:
            del settings[key]
        else:
            settings[key] = value
    with pytest.raises(ValueError):
        ColourMapper(distinct_map(), settings)


# ------------------------------------------------- general behaviour

def test_same_spectrum_gives_the_same_colour_every_time():
    mapper = make_mapper(distinct_map())
    first = mapper.map_colour(SPECTRA["many-bins"])
    assert mapper.map_colour(SPECTRA["many-bins"]) == first


def test_inputs_are_not_modified():
    cmap = distinct_map()
    settings = dict(SETTINGS)
    spectrum = list(SPECTRA["many-bins"])
    cmap_before, settings_before, spectrum_before = (
        copy.deepcopy(cmap), copy.deepcopy(settings), copy.deepcopy(spectrum),
    )
    make_mapper(cmap, settings).map_colour(spectrum)
    assert cmap == cmap_before
    assert settings == settings_before
    assert spectrum == spectrum_before


def test_settings_are_copied_at_construction():
    settings = dict(SETTINGS)
    mapper = make_mapper(distinct_map(), settings)
    before = mapper.map_colour(SPECTRA["many-bins"])
    settings["sample_rate"] = FS * 2
    settings["min_frequency"] = 50.0
    settings["max_magnitude"] = 0.01
    settings["floor_db"] = -90.0
    settings["extra"] = 1.0
    assert mapper.map_colour(SPECTRA["many-bins"]) == before


def test_colour_map_is_not_needed_after_construction():
    cmap = distinct_map()
    mapper = make_mapper(cmap)
    before = mapper.map_colour(SPECTRA["many-bins"])
    for row in cmap:
        row[:] = [(0, 0, 0)] * len(row)
    assert mapper.map_colour(SPECTRA["many-bins"]) == before


# ------------------------------------------------ CM-03: colour map templates

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "map"
MIN_TEMPLATES = 3
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp"}
TEMPLATE_FILES = (
    sorted(p for p in TEMPLATE_DIR.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    if TEMPLATE_DIR.is_dir()
    else []
)


def test_cm03_enough_templates_are_provided():
    assert len(TEMPLATE_FILES) >= MIN_TEMPLATES


@pytest.mark.parametrize("path", TEMPLATE_FILES, ids=lambda p: p.name)
def test_cm03_every_template_loads_and_produces_a_valid_colour(path):
    image_module = pytest.importorskip("PIL.Image")
    with image_module.open(path) as img:
        rgb = img.convert("RGB")
        width, height = rgb.size
        grid = [[rgb.getpixel((x, y)) for x in range(width)] for y in range(height)]
    assert grid and all(len(row) == width for row in grid)
    mapper = ColourMapper(grid, {"sample_rate": FS})
    assert_valid_colour(mapper.map_colour(SPECTRA["many-bins"]))
    assert mapper.map_colour(SPECTRA["all-zero"]) == (0, 0, 0)
