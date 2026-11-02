# Milestone 2: Requirements

## Capturing Audio

- 01: When the user presses Start, the application must capture playback audio from the computer's default output device.
- 02: The application shall supply captured samples in chronological order to the frequency analysis stage in chunks of time *t*. (*t* must be constant because bin frequencies depend on *t*)
- 03: When the user presses Stop, the application shall stop capturing audio.
- 04: Capturing audio shall not interrupt normal audio playback.
- 05: The user shall be able to restart capture after stopping it.
- 06: The application shall display whether capture is stopped, active, or in an error state.
- 07: There will always only be one capture session active so pressing start twice does not create an additional capture session.
- 08: Closing the application shall release the audio capture resources.

## FFT to Analyze Audio

- 01: The application shall divide captured audio into analysis windows containing N consecutive samples.
- 02: The application shall apply a Hann window function to each complete analysis window before computing its N-point FFT. 
- 03: Each analysis result shall contain frequency and magnitude pairs for bins k = 0 through floor(N / 2).
- 04: The frequency associated with bin k shall be k × fs / N Hz, where fs is the audio sample rate.
- 05: The magnitude associated with each bin shall be sqrt(real² + imaginary²) / N, where real and imaginary are the components of the unnormalized FFT output.

## Color Mapping

- 01: The application shall include all frequency bins produced by the frequency analysis stage in colour conversion.
- 02: The application shall map included frequencies to a colour map contained in an image file using linear mapping. 
- 03: The application will have multiple colour map templates provided.

## Display

- 01: While enabled, the overlay/light must display the latest colour produced by colour mapping. 
- 02: The colour displayed is the averaged value over the colour map.
- 03: When the user enables the overlay, the application shall show it until disabled.
- 04: When the user disables the overlay, the application shall hide it until enabled again.
- 05: If the application is closed, the display must not be open.

