"""ColourMapper tests (owner: Taj).

Requirements covered: CM-01, CM-02 (partly), CM-03, D-02 (partly).

The stubs do not say which keys `settings` needs, or how a
(frequency, magnitude) pair becomes a position on the colour map. So the
tests below only check things that hold for ANY sensible mapping:
  * a uniform map always gives that colour,
  * the result is an average of per-pair colours and stays inside the map's
    colour range,
  * every bin in the spectrum influences the result,
  * inputs are not modified and settings are copied.
The exact-colour tests for CM-02 and D-02 are skipped placeholders at the
bottom until the mapping is specified.
"""

import copy
import numbers
from pathlib import Path

import pytest

from lightmap.colour_mapper import ColourMapper

# TODO(Taj): put valid settings here once the colour-mapping design
# specification says which keys exist (e.g. maximum frequency and magnitude).
SETTINGS: dict[str, float] = {}


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


# ------------------------------------------------------ output is a colour

@pytest.mark.parametrize("name", SPECTRA)
def test_result_is_an_rgb_tuple_of_integers_0_to_255(name):
    assert_valid_colour(make_mapper(gradient_map()).map_colour(SPECTRA[name]))


# ------------------------------------------- D-02: the averaged colour

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


def test_d02_result_is_the_average_of_the_per_pair_colours():
    mapper = make_mapper(distinct_map())
    spectrum = [(0.0, 0.0), (500.0, 0.2), (5000.0, 0.9), (12000.0, 0.4), (23000.0, 1.0), (1e9, 1e9)]
    per_pair = [mapper._colour_for_pair(f, m) for f, m in spectrum]
    expected = [sum(colour[i] for colour in per_pair) / len(per_pair) for i in range(3)]
    result = mapper.map_colour(spectrum)
    for got, want in zip(result, expected):
        assert abs(got - want) <= 1.0        # allows rounding or truncation


def test_d02_a_single_pair_gives_that_pairs_colour():
    mapper = make_mapper(distinct_map())
    assert mapper.map_colour([(5000.0, 0.9)]) == mapper._colour_for_pair(5000.0, 0.9)


# --------------------------------------- CM-01: every bin is included

@pytest.mark.parametrize("length", [2, 9])
def test_cm01_every_position_in_the_spectrum_changes_the_result(length):
    """Replace one pair of an otherwise identical spectrum with a pair that
    lands on a different colour. The result must change wherever the replaced
    pair sits - including the first and last bins."""
    mapper = make_mapper(distinct_map())
    low, high = (0.0, 0.0), (1e9, 1e9)       # opposite edges of the map
    assert mapper._colour_for_pair(*low) != mapper._colour_for_pair(*high), (
        "test setup: these two pairs must map to different colours"
    )
    baseline = mapper.map_colour([low] * length)
    for k in range(length):
        spectrum = [low] * length
        spectrum[k] = high
        assert mapper.map_colour(spectrum) != baseline, f"bin {k} was ignored"


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
    # With SETTINGS empty this can only add a key, so it catches little. It
    # becomes a real check once SETTINGS holds the actual keys, because then
    # the loop below changes values the mapper depends on.
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


# --------------------------- CM-02 / D-02 exact colours: need the mapping spec

@pytest.mark.skip(
    reason="TODO: needs the mapping spec. Write once the settings keys and the "
    "(frequency, magnitude) -> pixel rule are fixed."
)
def test_cm02_two_pixel_black_and_white_map():
    """Map = one row [black, white]. The lowest frequency must land on the
    first pixel, the highest on the last, the midpoint in the middle (linear).
    Compare against colours calculated by hand, within +-1 per channel."""


@pytest.mark.skip(reason="TODO: needs the mapping spec (see above).")
def test_cm02_gradient_and_custom_maps_match_hand_computed_colours():
    """Gradient map, then a custom map with known pixels; hand-computed
    expected colours, +-1 per channel."""


@pytest.mark.skip(reason="TODO: needs the averaging formula decided (checklist section 0).")
def test_d02_hand_computed_spectra_give_the_expected_average():
    """A few small spectra whose averaged colour you worked out by hand."""


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
