from math import floor, isfinite, log, log10

from .preferences import AudioTuning

# A colour map image as a rectangular grid of RGB pixels, indexed [row][column]
# (row 0 is the top row, last row is the bottom row;
# column 0 is the leftmost column, last column is the rightmost column).
ColourMapImage = list[list[tuple[int, int, int]]]

DEFAULT_MAX_MAGNITUDE = 0.5
DEFAULT_FLOOR_DB = -60.0
DEFAULT_MIN_FREQUENCY = 20.0


class ColourMapper:
    def __init__(
        self, colour_map: ColourMapImage, settings: dict[str, float]
    ) -> None:
        """
        Preconditions:
            colour_map is a nonempty rectangular grid of
            (red, green, blue) pixels indexed [row][column], each
            channel an integer from 0 to 255.
            settings satisfies the colour-mapping design specification:
              - `sample_rate` (fs, required): finite and positive. The
                horizontal axis ends at fs / 2.
              - `min_frequency` (default 20 Hz): finite, positive, and
                below fs / 2. The horizontal axis starts here.
              - `max_magnitude` (default 0.5): finite and positive. The
                0 dB reference, at the top row.
              - `floor_db` (default -60 dB): finite and negative. The
                bottom row; quieter bins are excluded from the colour.
        Postconditions:
            colour_map is processed once into a 2D lookup grid used for
            all later lookups; it is not needed after construction.
            The mapper is configured using a copy of settings, with
            defaults filled in for omitted optional settings.
            The supplied colour_map and settings are unchanged.
        Raises:
            ValueError if colour_map is empty or not rectangular, or a
            setting is missing or out of range.
        """
        if not colour_map or not colour_map[0] or any(
            len(row) != len(colour_map[0]) for row in colour_map
        ):
            raise ValueError("colour map must be a nonempty rectangular grid")

        self._settings = {
            "min_frequency": DEFAULT_MIN_FREQUENCY,
            "max_magnitude": DEFAULT_MAX_MAGNITUDE,
            "floor_db": DEFAULT_FLOOR_DB,
            **settings,
        }
        for key in ("sample_rate", "min_frequency", "max_magnitude", "floor_db"):
            value = self._settings.get(key)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            ):
                raise ValueError(f"colour map {key} must be a finite number")

        self._nyquist = self._settings["sample_rate"] / 2
        self._min_frequency = self._settings["min_frequency"]
        self._max_magnitude = self._settings["max_magnitude"]
        self._floor_db = self._settings["floor_db"]
        if self._nyquist <= 0:
            raise ValueError("colour map sample_rate must be positive")
        if not 0 < self._min_frequency < self._nyquist:
            raise ValueError("colour map min_frequency must be in (0, sample_rate / 2)")
        if self._max_magnitude <= 0:
            raise ValueError("colour map max_magnitude must be positive")
        if self._floor_db >= 0:
            raise ValueError("colour map floor_db must be negative")

        self._grid = self._build_lookup_grid(colour_map)
        self._last_row = len(self._grid) - 1
        self._last_column = len(self._grid[0]) - 1
        self._log_frequency_span = log(self._nyquist / self._min_frequency)
        # Magnitudes below this are under the floor. The tiny allowance keeps
        # a magnitude exactly at the floor from being lost to rounding.
        self._floor_magnitude = self._max_magnitude * 10 ** (self._floor_db / 20) * (1 - 1e-12)

    def map_colour(
        self, spectrum: list[tuple[float, float]], *, tuning: AudioTuning | None = None
    ) -> tuple[int, int, int]:
        """
        Preconditions:
            spectrum is nonempty.
            Each pair contains a finite, nonnegative frequency
            and a finite, nonnegative magnitude.
        Postconditions:
            Returns one (red, green, blue) colour, each an integer from
            0 to 255, for the whole analysis result: the power-weighted
            (magnitude squared) mean RGB of the colours that the 2D
            colour map gives for each frequency-magnitude pair in
            spectrum at or above the floor (accurate within +/-1 per
            RGB channel). Pairs below the floor are excluded.
            With tuning, use its floor and frequency-band power weights.
            With no contributing bins, return the quiet colour (black by default).
            spectrum, the lookup grid, and the mapper's settings are
            unchanged.
        """
        total_weight = 0.0
        sums = [0.0, 0.0, 0.0]
        floor_db = self._floor_db if tuning is None else tuning.floor_db
        floor_magnitude = self._floor_magnitude
        if floor_db != self._floor_db:
            floor_magnitude = self._max_magnitude * 10 ** (floor_db / 20) * (1 - 1e-12)
        for frequency, magnitude in spectrum:
            if magnitude < floor_magnitude:
                continue
            weight = magnitude * magnitude
            if tuning is not None:
                weight *= tuning.weight(frequency)
            if weight == 0:
                continue
            colour = self._lookup(frequency, magnitude, floor_db)
            total_weight += weight
            for channel in range(3):
                sums[channel] += weight * colour[channel]

        if total_weight == 0:
            return (0, 0, 0) if tuning is None else tuning.quiet_colour
        red, green, blue = (_to_channel(total / total_weight) for total in sums)
        return (red, green, blue)

    def _build_lookup_grid(
        self, colour_map: ColourMapImage
    ) -> ColourMapImage:
        """
        Preconditions:
            colour_map satisfies the __init__ preconditions.
        Postconditions:
            Returns an independent 2D [row][column] lookup grid of the
            image's RGB pixels suitable for mapping frequency-magnitude
            pairs (horizontal axis: log frequency, min_frequency = first
            column, fs / 2 = last column; vertical axis: decibels,
            floor_db = bottom row, 0 dB (max_magnitude) = top row).
            Called once, from __init__.
            colour_map is unchanged.
        """
        return [[tuple(pixel) for pixel in row] for row in colour_map]

    def _colour_for_pair(
        self, frequency: float, magnitude: float
    ) -> tuple[int, int, int]:
        """
        Preconditions:
            frequency and magnitude are finite and nonnegative.
        Postconditions:
            Returns the (red, green, blue) colour the 2D lookup grid
            gives for this frequency-magnitude pair, each an integer
            from 0 to 255 (accurate within +/-1 per RGB channel):
              - Horizontal axis (frequency): logarithmic from
                min_frequency (first / leftmost column) to fs / 2
                (last / rightmost column).
              - Vertical axis (magnitude in dB relative to
                max_magnitude): linear in dB from floor_db (bottom row)
                to 0 dB (top row).
              - Values outside [min_frequency, fs / 2] or
                [floor_db, 0 dB] (including 0 Hz and magnitude 0) are
                clamped to the nearest edge of the image.
              - Pixel centres are the sample points; a point falling
                between pixel centres gets the per-channel bilinear
                interpolation of the (up to four) surrounding pixels.
                An image one pixel tall or wide is constant along that
                axis.
        """
        red, green, blue = (_to_channel(value) for value in self._lookup(frequency, magnitude))
        return (red, green, blue)

    def _lookup(
        self, frequency: float, magnitude: float, floor_db: float | None = None
    ) -> tuple[float, float, float]:
        """Return the unrounded bilinear colour at this pair's position."""
        if frequency <= self._min_frequency:
            u = 0.0
        else:
            u = min(log(frequency / self._min_frequency) / self._log_frequency_span, 1.0)
        if magnitude <= 0:
            v = 0.0
        else:
            decibels = 20 * log10(magnitude / self._max_magnitude)
            v = min(max(1 - decibels / (self._floor_db if floor_db is None else floor_db), 0.0), 1.0)

        x = u * self._last_column
        y = (1 - v) * self._last_row
        left, top = floor(x), floor(y)
        right, bottom = min(left + 1, self._last_column), min(top + 1, self._last_row)
        dx, dy = x - left, y - top

        upper, lower = self._grid[top], self._grid[bottom]
        return tuple(
            (1 - dy) * ((1 - dx) * upper[left][c] + dx * upper[right][c])
            + dy * ((1 - dx) * lower[left][c] + dx * lower[right][c])
            for c in range(3)
        )


def _to_channel(value: float) -> int:
    """Round to the nearest integer channel value from 0 to 255."""
    return min(max(floor(value + 0.5), 0), 255)
