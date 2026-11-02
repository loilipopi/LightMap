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
            settings satisfies the colour-mapping design specification.
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
            0 to 255, for the whole analysis result: the average of the
            colours that the linear map gives for each
            frequency-magnitude pair in spectrum.
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
            table suitable for mapping frequency-magnitude pairs.
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
            0 to 255.
            Values beyond the map's range are clamped to its edge.
        """
        raise NotImplementedError
