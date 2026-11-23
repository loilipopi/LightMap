# A colour map image as a rectangular grid of RGB pixels, indexed [row][column].
ColourMapImage = list[list[tuple[int, int, int]]]


class ColourMapper:
    def __init__(
        self, colour_map: ColourMapImage, settings: dict[str, float]
    ) -> None:
        """
        Preconditions:
            colour_map is a nonempty rectangular grid of
            (red, green, blue) pixels, each channel an integer
            from 0 to 255.
            settings satisfies the colour-mapping design specification
            (including sample rate fs defining the frequency axis
            [0 Hz, fs / 2]).
        Postconditions:
            colour_map is processed once into a linear map used for
            all later lookups; it is not needed after construction.
            The mapper is configured using a copy of settings.
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
            magnitude-weighted mean RGB of the colours that the linear
            map gives for each frequency-magnitude pair in spectrum
            (accurate within +/-1 per RGB channel).
            If the sum of all magnitudes in spectrum is zero, returns
            the unweighted mean RGB of the mapped colours.
            spectrum, the linear map, and the mapper's settings are
            unchanged.
        """
        raise NotImplementedError

    def _build_linear_map(
        self, colour_map: ColourMapImage
    ) -> list[tuple[int, int, int]]:
        """
        Preconditions:
            colour_map satisfies the __init__ preconditions.
        Postconditions:
            Returns the image's colours as a linear (flat) lookup
            table suitable for mapping frequency-magnitude pairs,
            with frequency mapped linearly across the colour map's
            frequency axis (0 Hz = first pixel, fs / 2 = last pixel).
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
            Returns the (red, green, blue) colour the linear map gives
            for this frequency-magnitude pair, each an integer from
            0 to 255 (accurate within +/-1 per RGB channel).
            Frequency maps linearly from 0 Hz (first pixel) to fs / 2
            (last pixel); values beyond the map's range are clamped to
            its edge.
        """
        raise NotImplementedError
