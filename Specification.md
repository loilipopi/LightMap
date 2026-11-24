## Problem
Individuals with poor hearing cant play video games that make use of important audio ques. These video games become inaccessible or significantly more difficult to play for these individuals. 

## Solution
We want to create a tool where PC audio is captured and processed with a FFT to create a Volume vs Frequency map. In real time, each frequency bin is placed on a 2D colour map image, with frequency on the horizontal axis and magnitude on the vertical axis. Bins too quiet to matter are ignored, and the colours the remaining bins land on are combined into one single colour, with louder bins counting for more. This will then be outputted to either an overlay or an external light.

<img width="955" height="455" alt="image" src="https://github.com/user-attachments/assets/58797190-01c4-4eaa-9415-030f20fd47b4" />
Additionally, the user can create their own custom colour map for whatever scenario and game they want, ideally this should be easy to make but is outside the scope of this project.


For example in a game like Valorant, there is an objective emits a sound periodically which gets faster as it nears the end of the timer. Not being able to hear that sound is detrimental as can't tell how much time is left. What our software will do is take that sound convert it to a colour and output it to the user.

## Technical Specifications
- **Window size and chunk duration:** Window size `N = 1024` samples and chunk duration `t = N / fs` (where `fs` is the audio sample rate in Hz), so one chunk equals one analysis window with no overlap.
- **Hann window:** Periodic Hann window `w[n] = 0.5 * (1 - cos(2πn / N))` for `n = 0, ..., N - 1`, applied to each complete analysis window before computing the N-point FFT.
- **FFT output:** Frequency–magnitude pairs for bins `k = 0` through `floor(N / 2)`, with bin frequency `k × fs / N` Hz and magnitude `sqrt(real² + imaginary²) / N`.
- **Colour map axes:** The colour map is a 2D image (row 0 is the top). Each frequency–magnitude pair selects one point on it:
  - **Horizontal axis = frequency:** logarithmic, where `min_frequency` corresponds to the first (leftmost) column and `fs / 2` to the last (rightmost) column. Position across is `log(f / min_frequency) / log((fs / 2) / min_frequency)`, so each doubling of frequency moves the same distance.
  - **Vertical axis = magnitude in decibels:** `dB = 20 × log10(magnitude / max_magnitude)`, mapped linearly from `floor_db` at the bottom row to `0 dB` at the top row.
  - Values outside these ranges (including `0 Hz`, which is below `min_frequency`) are clamped to the nearest edge of the image.
- **Colour-mapping settings:**
  - `sample_rate` (`fs`): required.
  - `min_frequency`: default `20 Hz`, the low end of human hearing. Must be above 0 and below `fs / 2`.
  - `max_magnitude`: the `0 dB` reference. Default `0.5`, the largest bin magnitude possible for samples in `[-1, 1]` with the periodic Hann window.
  - `floor_db`: the noise floor and bottom row. Default `-60 dB`. Must be negative.
- **Noise floor:** Bins quieter than `floor_db` are excluded from the colour. A bin exactly at the floor is included.
- **Interpolation between pixels:** Pixel centres are the sample points of the map. A point that falls between pixel centres gets the bilinear interpolation of the (up to four) surrounding pixels, computed per RGB channel. For example, on a one-row `[black, white]` map, the frequency halfway along the log axis gives `(127.5, 127.5, 127.5)`. An image one pixel tall (or wide) has a constant colour along that axis.
- **Colour averaging (D-02):** Power-weighted mean RGB of the colours that the bins at or above the floor map to, where each bin's weight is `magnitude²`. If no bin is at or above the floor (silence), the output is black `(0, 0, 0)`. The output is rounded to the nearest integer per channel.
- **Colour tolerances:** `±1` per RGB channel for `ColorMapper`, and `±2` per RGB channel for overlay screenshots.
