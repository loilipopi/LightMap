"""ColourMapper tests (owner: Taj).

Requirements covered: CM-01, CM-02, CM-03, D-02.

Confirmed specification:
  * Frequency axis of the colour map: linear mapping where
    0 Hz = first pixel and fs / 2 = last pixel.
  * D-02 averaging formula: magnitude-weighted mean RGB of the colours
    that the frequency bins map to.
  * Colour tolerance: +-1 per RGB channel for ColourMapper.
"""

import copy
import numbers
from pathlib import Path

import pytest

from lightmap.colour_mapper import ColourMapper

FS = 48000.0
NYQUIST = FS / 2.0
CHANNEL_TOLERANCE = 1

# Update the key name here if ColourMapper expects a different settings key for fs.
SETTINGS: dict[str, float] = {"sample_rate": FS}


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


SPECTRA = {
    "single-low": [(0.0, 0.0)],
    "single-mid": [(1000.0, 0.5)],
    "beyond-range": [(1e9, 1e9)],
    "many-bins": [(f * 100.0, (f % 7) * 0.1) for f in range(60)],
}


def assert_valid_colour(colour):
    assert isinstance(colour, tuple) and len(colour) == 3
    for channel in colour:
        assert isinstance(channel, numbers.Integral)
        assert 0 <= channel <= 255


def assert_colour_close(actual, expected, tolerance=CHANNEL_TOLERANCE):
    assert_valid_colour(actual)
    for got, want in zip(actual, expected):
        assert abs(got - want) <= tolerance


# ------------------------------------------------------ output is a colour

@pytest.mark.parametrize("name", SPECTRA)
def test_result_is_an_rgb_tuple_of_integers_0_to_255(name):
    assert_valid_colour(make_mapper(gradient_map()).map_colour(SPECTRA[name]))


# ------------------------------------------- D-02: magnitude-weighted mean RGB

@pytest.mark.parametrize("name", SPECTRA)
def test_d02_uniform_map_gives_that_colour_for_any_spectrum(name):
    """Independent of the averaging formula: averaging identical colours
    must give that colour."""
    assert make_mapper(uniform_map((10, 20, 30))).map_colour(SPECTRA[name]) == (10, 20, 30)


@pytest.mark.parametrize("name", SPECTRA)
def test_d02_result_stays_inside_the_colour_range_of_the_map(name):
    cmap = gradient_map()
    result = make_mapper(cmap).map_colour(SPECTRA[name])
    for channel in range(3):
        values = [pixel[channel] for row in cmap for pixel in row]
        assert min(values) <= result[channel] <= max(values)


def test_d02_result_is_the_magnitude_weighted_mean_of_the_per_pair_colours():
    mapper = make_mapper(distinct_map())
    spectrum = [
        (0.0, 0.1),
        (500.0, 0.2),
        (5000.0, 0.9),
        (12000.0, 0.4),
        (NYQUIST, 1.0),
    ]
    per_pair = [mapper._colour_for_pair(f, m) for f, m in spectrum]
    total_mag = sum(m for _, m in spectrum)
    expected = [
        sum(m * colour[i] for (_, m), colour in zip(spectrum, per_pair)) / total_mag
        for i in range(3)
    ]
    result = mapper.map_colour(spectrum)
    assert_colour_close(result, expected)


def test_d02_a_single_pair_gives_that_pairs_colour():
    mapper = make_mapper(distinct_map())
    assert mapper.map_colour([(5000.0, 0.9)]) == mapper._colour_for_pair(5000.0, 0.9)


def test_d02_hand_computed_spectra_give_the_expected_magnitude_weighted_average():
    """Hand-computed magnitude-weighted mean RGB over a 3-pixel custom map
    where 0 Hz -> red (255, 0, 0), fs/4 -> green (0, 255, 0),
    and fs/2 -> blue (0, 0, 255)."""
    rgb_map = [[(255, 0, 0), (0, 255, 0), (0, 0, 255)]]
    mapper = make_mapper(rgb_map)

    # Equal magnitudes (1, 1, 1) -> (85, 85, 85)
    assert_colour_close(
        mapper.map_colour([(0.0, 1.0), (FS / 4, 1.0), (NYQUIST, 1.0)]),
        (85.0, 85.0, 85.0),
    )
    # Weights 3:1 between red and blue -> (191.25, 0.0, 63.75)
    assert_colour_close(
        mapper.map_colour([(0.0, 3.0), (NYQUIST, 1.0)]),
        (191.25, 0.0, 63.75),
    )
    # Weights 1:2:5 -> R=255/8=31.875, G=510/8=63.75, B=1275/8=159.375
    assert_colour_close(
        mapper.map_colour([(0.0, 1.0), (FS / 4, 2.0), (NYQUIST, 5.0)]),
        (31.875, 63.75, 159.375),
    )
    # Zero-magnitude bin has weight 0; positive bin determines output
    assert_colour_close(
        mapper.map_colour([(0.0, 0.0), (FS / 4, 2.5)]),
        (0.0, 255.0, 0.0),
    )


# --------------------------------------- CM-01: every bin is included

@pytest.mark.parametrize("length", [2, 9, 513])
def test_cm01_every_position_in_the_spectrum_changes_the_result(length):
    """Replace one pair of an otherwise identical spectrum with a pair that
    lands on a different colour. The result must change wherever the replaced
    pair sits - including the first (k=0) and last (k=floor(N/2)) bins."""
    mapper = make_mapper(distinct_map())
    low, high = (0.0, 0.01), (NYQUIST, 10.0)   # opposite edges of [0 Hz, fs/2]
    assert mapper._colour_for_pair(*low) != mapper._colour_for_pair(*high), (
        "test setup: these two pairs must map to different colours"
    )
    baseline = mapper.map_colour([low] * length)
    for k in range(length):
        spectrum = [low] * length
        spectrum[k] = high
        assert mapper.map_colour(spectrum) != baseline, f"bin {k} was ignored"


# ----------------------------------------- CM-02: linear frequency-axis map

def test_cm02_two_pixel_black_and_white_map():
    """Map = one row [black, white]. 0 Hz maps to the first pixel (black),
    fs / 2 to the last pixel (white), and fs / 4 to the midpoint (linear),
    each within +-1 per RGB channel."""
    bw_map = [[(0, 0, 0), (255, 255, 255)]]
    mapper = make_mapper(bw_map)

    assert_colour_close(mapper.map_colour([(0.0, 1.0)]), (0.0, 0.0, 0.0))
    assert_colour_close(mapper.map_colour([(NYQUIST, 1.0)]), (255.0, 255.0, 255.0))
    assert_colour_close(mapper.map_colour([(FS / 4, 1.0)]), (127.5, 127.5, 127.5))


def test_cm02_gradient_and_custom_maps_match_hand_computed_colours():
    """Gradient map and custom map with known pixels; hand-computed expected
    colours along [0 Hz, fs / 2], within +-1 per RGB channel."""
    # 4-pixel linear gradient: pixels at 0, fs/6, fs/3, fs/2
    grad = [[(0, 255, 0), (85, 170, 85), (170, 85, 170), (255, 0, 255)]]
    grad_mapper = make_mapper(grad)
    assert_colour_close(grad_mapper.map_colour([(0.0, 1.0)]), (0.0, 255.0, 0.0))
    assert_colour_close(grad_mapper.map_colour([(FS / 6, 1.0)]), (85.0, 170.0, 85.0))
    assert_colour_close(grad_mapper.map_colour([(FS / 4, 1.0)]), (127.5, 127.5, 127.5))
    assert_colour_close(grad_mapper.map_colour([(FS / 3, 1.0)]), (170.0, 85.0, 170.0))
    assert_colour_close(grad_mapper.map_colour([(NYQUIST, 1.0)]), (255.0, 0.0, 255.0))

    # 3-pixel custom map: red at 0 Hz, green at fs/4, blue at fs/2
    custom = [[(255, 0, 0), (0, 255, 0), (0, 0, 255)]]
    custom_mapper = make_mapper(custom)
    assert_colour_close(custom_mapper.map_colour([(0.0, 1.0)]), (255.0, 0.0, 0.0))
    assert_colour_close(custom_mapper.map_colour([(FS / 8, 1.0)]), (127.5, 127.5, 0.0))
    assert_colour_close(custom_mapper.map_colour([(FS / 4, 1.0)]), (0.0, 255.0, 0.0))
    assert_colour_close(custom_mapper.map_colour([(3 * FS / 8, 1.0)]), (0.0, 127.5, 127.5))
    assert_colour_close(custom_mapper.map_colour([(NYQUIST, 1.0)]), (0.0, 0.0, 255.0))


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
    for key in list(settings):
        settings[key] = settings[key] * 2 + 1
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

# TODO(Taj): point this at the folder that holds the shipped colour maps.
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "colour_maps"
MIN_TEMPLATES = 3
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp"}
TEMPLATE_FILES = (
    sorted(p for p in TEMPLATE_DIR.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    if TEMPLATE_DIR.is_dir()
    else []
)


@pytest.mark.skipif(not TEMPLATE_DIR.is_dir(), reason=f"no templates folder at {TEMPLATE_DIR}; set TEMPLATE_DIR")
def test_cm03_enough_templates_are_provided():
    assert len(TEMPLATE_FILES) >= MIN_TEMPLATES


@pytest.mark.parametrize("path", TEMPLATE_FILES, ids=lambda p: p.name)
def test_cm03_every_template_loads_and_produces_a_valid_colour(path):
    image_module = pytest.importorskip("PIL.Image")
    with image_module.open(path) as img:
        rgb = img.convert("RGB")
        width, height = rgb.size
        pixels = list(rgb.getdata())
    grid = [pixels[r * width:(r + 1) * width] for r in range(height)]
    assert grid and all(len(row) == width for row in grid)
    assert_valid_colour(make_mapper(grid).map_colour(SPECTRA["many-bins"]))
