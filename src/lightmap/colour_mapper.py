from math import floor, isfinite, log, log10

from .preferences import AudioTuning

# A colour map image as a rectangular grid of RGB pixels, indexed [row][column]
# (row 0 is the top row, last row is the bottom row;
# column 0 is the leftmost column, last column is the rightmost column).
ColourMapImage = list[list[tuple[int, int, int]]]

DEFAULT_MAX_MAGNITUDE = 0.5
DEFAULT_FLOOR_DB = -60.0
DEFAULT_MIN_FREQUENCY = 20.0
_MAX_FREQ_CACHE = 8192


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
        self._freq_cache: dict[float, tuple[int, int, float]] = {}
        self._gain_key: tuple[int, int, int] | None = None
        self._gain_cache: dict[float, float] = {}

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
            With tuning, use its floor and perceptual frequency-band gains
            for floor gating, vertical dB lookup, and power weighting.
            With no contributing bins, return the quiet colour (black by default).
            spectrum, the lookup grid, and the mapper's settings are
            unchanged.
        """
        total_weight = 0.0
        sum_r = 0.0
        sum_g = 0.0
        sum_b = 0.0
        floor_db = self._floor_db if tuning is None else tuning.floor_db
        floor_magnitude = self._floor_magnitude
        if floor_db != self._floor_db:
            floor_magnitude = self._max_magnitude * 10 ** (floor_db / 20) * (1 - 1e-12)

        apply_gain = (
            tuning is not None
            and not (tuning.low == 100 and tuning.mid == 100 and tuning.high == 100)
        )
        gain_cache: dict[float, float] | None = None
        if apply_gain:
            assert tuning is not None
            key = (tuning.low, tuning.mid, tuning.high)
            if self._gain_key != key:
                self._gain_key = key
                self._gain_cache.clear()
            gain_cache = self._gain_cache

        grid = self._grid
        last_row = self._last_row
        inv_max_mag = 1.0 / self._max_magnitude
        inv_floor_db = 1.0 / floor_db
        freq_cache = self._freq_cache
        x_lookup = self._x_position

        for frequency, magnitude in spectrum:
            if apply_gain:
                assert tuning is not None and gain_cache is not None
                gain = gain_cache.get(frequency)
                if gain is None:
                    gain = tuning.gain(frequency)
                    if len(gain_cache) >= _MAX_FREQ_CACHE:
                        gain_cache.clear()
                    gain_cache[frequency] = gain
                magnitude *= gain
            if magnitude < floor_magnitude:
                continue
            weight = magnitude * magnitude

            pos = freq_cache.get(frequency)
            if pos is None:
                pos = x_lookup(frequency)
                if len(freq_cache) >= _MAX_FREQ_CACHE:
                    freq_cache.clear()
                freq_cache[frequency] = pos
            left, right, dx = pos

            if last_row == 0:
                row = grid[0]
                p0 = row[left]
                p1 = row[right]
                omx = 1.0 - dx
                r = omx * p0[0] + dx * p1[0]
                g = omx * p0[1] + dx * p1[1]
                b = omx * p0[2] + dx * p1[2]
            else:
                decibels = 20.0 * log10(magnitude * inv_max_mag)
                v = 1.0 - decibels * inv_floor_db
                if v < 0.0:
                    v = 0.0
                elif v > 1.0:
                    v = 1.0
                y = (1.0 - v) * last_row
                top = int(y)
                bottom = top + 1 if top < last_row else last_row
                dy = y - top
                omy = 1.0 - dy
                omx = 1.0 - dx
                upper = grid[top]
                lower = grid[bottom]
                ul = upper[left]
                ur = upper[right]
                ll = lower[left]
                lr = lower[right]
                r = omy * (omx * ul[0] + dx * ur[0]) + dy * (omx * ll[0] + dx * lr[0])
                g = omy * (omx * ul[1] + dx * ur[1]) + dy * (omx * ll[1] + dx * lr[1])
                b = omy * (omx * ul[2] + dx * ur[2]) + dy * (omx * ll[2] + dx * lr[2])

            total_weight += weight
            sum_r += weight * r
            sum_g += weight * g
            sum_b += weight * b

        if total_weight == 0:
            return (0, 0, 0) if tuning is None else tuning.quiet_colour
        inv_weight = 1.0 / total_weight
        return (
            _to_channel(sum_r * inv_weight),
            _to_channel(sum_g * inv_weight),
            _to_channel(sum_b * inv_weight),
        )

    def _x_position(self, frequency: float) -> tuple[int, int, float]:
        if frequency <= self._min_frequency:
            u = 0.0
        else:
            u = log(frequency / self._min_frequency) / self._log_frequency_span
            if u > 1.0:
                u = 1.0
        x = u * self._last_column
        left = floor(x)
        right = left + 1 if left < self._last_column else self._last_column
        return left, right, x - left

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
        left, right, dx = self._x_position(frequency)
        if magnitude <= 0:
            v = 0.0
        else:
            decibels = 20 * log10(magnitude / self._max_magnitude)
            v = min(max(1 - decibels / (self._floor_db if floor_db is None else floor_db), 0.0), 1.0)

        y = (1 - v) * self._last_row
        top = floor(y)
        bottom = min(top + 1, self._last_row)
        dy = y - top

        upper, lower = self._grid[top], self._grid[bottom]
        omx, omy = 1 - dx, 1 - dy
        ul, ur, ll, lr = upper[left], upper[right], lower[left], lower[right]
        return (
            omy * (omx * ul[0] + dx * ur[0]) + dy * (omx * ll[0] + dx * lr[0]),
            omy * (omx * ul[1] + dx * ur[1]) + dy * (omx * ll[1] + dx * lr[1]),
            omy * (omx * ul[2] + dx * ur[2]) + dy * (omx * ll[2] + dx * lr[2]),
        )


def _to_channel(value: float) -> int:
    """Round to the nearest integer channel value from 0 to 255."""
    return min(max(floor(value + 0.5), 0), 255)
