# Milestone 2: Requirements

## Capturing Audio

- 01: When the user presses Start, the application must capture playback audio from the computer's default output device.
- 02: The application shall supply captured samples in chronological order to the frequency analysis stage in chunks of time *t* = *N* / *fs*, where *N* = 1024 samples and *fs* is the audio sample rate (one chunk = one analysis window, no overlap; *t* must be constant because bin frequencies depend on *t*).
- 03: When the user presses Stop, the application shall stop capturing audio.
- 04: Capturing audio shall not interrupt normal audio playback.
- 05: The user shall be able to restart capture after stopping it.
- 06: The application shall display whether capture is stopped, active, or in an error state.
- 07: There will always only be one capture session active so pressing start twice does not create an additional capture session.
- 08: Closing the application shall release the audio capture resources.

## FFT to Analyze Audio

- 01: The application shall divide captured audio into analysis windows containing *N* = 1024 consecutive samples (non-overlapping when supplied in chunks of duration *t* = *N* / *fs*).
- 02: The application shall apply a periodic Hann window function, `w[n] = 0.5 * (1 - cos(2πn / N))` for `n = 0, ..., N - 1`, to each complete analysis window before computing its *N*-point FFT.
- 03: Each analysis result shall contain frequency and magnitude pairs for bins `k = 0` through `floor(N / 2)`.
- 04: The frequency associated with bin `k` shall be `k × fs / N` Hz, where `fs` is the audio sample rate.
- 05: The magnitude associated with each bin shall be `sqrt(real² + imaginary²) / N`, where `real` and `imaginary` are the components of the unnormalized FFT output.

## Color Mapping

- 01: The application shall include every frequency bin produced by the frequency analysis stage whose magnitude is at or above the noise floor (`floor_db`, default `-60 dB` relative to `max_magnitude`) in colour conversion, and exclude bins below it.
- 02: The application shall map each included frequency–magnitude pair to a colour on a 2D colour map contained in an image file: frequency maps logarithmically to the horizontal axis (`min_frequency`, default `20 Hz`, = first column, `fs / 2` = last column) and magnitude in decibels maps linearly to the vertical axis (`floor_db` = bottom row, `0 dB` = `max_magnitude` = top row). Values outside these ranges are clamped to the edge, and colours between pixel centres are bilinearly interpolated (accurate within `±1` per RGB channel for `ColorMapper`).
- 03: The application will have multiple colour map templates provided.

## Display

- 01: While enabled, the overlay/light must display the latest colour produced by colour mapping (accurate within `±2` per RGB channel in overlay screenshots).
- 02: The colour displayed is the power-weighted (magnitude²) mean RGB of the colours that the included frequency bins map to on the colour map, or black when no bin is included (accurate within `±1` per RGB channel for `ColorMapper`).
- 03: When the user enables the overlay, the application shall show it until disabled.
- 04: When the user disables the overlay, the application shall hide it until enabled again.
- 05: If the application is closed, the display must not be open.
