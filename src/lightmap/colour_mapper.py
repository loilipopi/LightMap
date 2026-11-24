# A colour map image as a rectangular grid of RGB pixels, indexed [row][column]
# (row 0 is the top row, last row is the bottom row;
# column 0 is the leftmost column, last column is the rightmost column).
ColourMapImage = list[list[tuple[int, int, int]]]


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
            it includes a finite, positive sample rate `sample_rate`
            (fs) defining the horizontal frequency axis [0 Hz, fs / 2],
            and optionally a finite, positive `max_magnitude` (default
            0.5) defining the vertical magnitude axis
            [0, max_magnitude].
        Postconditions:
            colour_map is processed once into a 2D lookup grid used for
            all later lookups; it is not needed after construction.
            The mapper is configured using a copy of settings
            (defaulting `max_magnitude` to 0.5 when omitted).
            The supplied colour_map and settings are unchanged.
        """
        raise NotImplementedError

    def map_colour(
        self, spectrum: list[tuple[float, float]]
    ) -> tuple[int, int, int]:
        """
        Preconditions:
            spectrum is nonempty.
            Each pair contains a finite, nonnegative frequency
            and a finite, nonnegative magnitude.
        Postconditions:
            Returns one (red, green, blue) colour, each an integer from
            0 to 255, for the whole analysis result: the
            magnitude-weighted mean RGB of the colours that the 2D
            colour map gives for each frequency-magnitude pair in
            spectrum (accurate within +/-1 per RGB channel).
            Magnitude is used both for the vertical position on the 2D
            map and as the weight in the average.
            If the sum of all magnitudes in spectrum is zero, returns
            the unweighted mean RGB of the mapped colours.
            spectrum, the lookup grid, and the mapper's settings are
            unchanged.
        """
        raise NotImplementedError

    def _build_lookup_grid(
        self, colour_map: ColourMapImage
    ) -> ColourMapImage:
        """
        Preconditions:
            colour_map satisfies the __init__ preconditions.
        Postconditions:
            Returns an independent 2D [row][column] lookup grid of the
            image's RGB pixels suitable for mapping frequency-magnitude
            pairs (horizontal axis: frequency, 0 Hz = first column,
            fs / 2 = last column; vertical axis: magnitude, 0 = bottom
            row, max_magnitude = top row).
            Called once, from __init__.
            colour_map is unchanged.
        """
        raise NotImplementedError

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
              - Horizontal axis (frequency): linear from 0 Hz (first /
                leftmost column) to fs / 2 (last / rightmost column).
              - Vertical axis (magnitude): linear from 0 (bottom row)
                to max_magnitude (top row).
              - Values outside [0 Hz, fs / 2] or [0, max_magnitude] are
                clamped to the nearest edge of the image.
              - Pixel centres are the sample points; a point falling
                between pixel centres gets the per-channel bilinear
                interpolation of the (up to four) surrounding pixels.
                An image one pixel tall or wide is constant along that
                axis.
        """
        raise NotImplementedError
