## Problem
Individuals with poor hearing cant play video games that make use of important audio ques. These video games become inaccessible or significantly more difficult to play for these individuals. 

## Solution
We want to create a tool where PC audio is captured and processed with a FFT to create a Volume vs Frequency map. In real time, each frequency bin is placed on a 2D colour map image, with frequency on the horizontal axis and magnitude on the vertical axis. The colours the bins land on are combined into one single colour, weighted by magnitude. This will then be outputted to either an overlay or an external light.

<img width="955" height="455" alt="image" src="https://github.com/user-attachments/assets/58797190-01c4-4eaa-9415-030f20fd47b4" />
Additionally, the user can create their own custom colour map for whatever scenario and game they want, ideally this should be easy to make but is outside the scope of this project.


For example in a game like Valorant, there is an objective emits a sound periodically which gets faster as it nears the end of the timer. Not being able to hear that sound is detrimental as can't tell how much time is left. What our software will do is take that sound convert it to a colour and output it to the user.

## Technical Specifications
- **Window size and chunk duration:** Window size `N = 1024` samples and chunk duration `t = N / fs` (where `fs` is the audio sample rate in Hz), so one chunk equals one analysis window with no overlap.
- **Hann window:** Periodic Hann window `w[n] = 0.5 * (1 - cos(2πn / N))` for `n = 0, ..., N - 1`, applied to each complete analysis window before computing the N-point FFT.
- **FFT output:** Frequency–magnitude pairs for bins `k = 0` through `floor(N / 2)`, with bin frequency `k × fs / N` Hz and magnitude `sqrt(real² + imaginary²) / N`.
- **Colour map axes:** The colour map is a 2D image. Each frequency–magnitude pair selects one point on it:
  - **Horizontal axis = frequency:** linear, where `0 Hz` corresponds to the first (leftmost) column and `fs / 2` to the last (rightmost) column.
  - **Vertical axis = magnitude:** linear, where magnitude `0` corresponds to the bottom row and `max_magnitude` to the top row.
  - Values outside these ranges are clamped to the nearest edge of the image.
- **Magnitude axis range:** `max_magnitude` is a colour-mapping setting. Default `0.5`, the largest bin magnitude possible for samples in `[-1, 1]` with the periodic Hann window.
- **Interpolation between pixels:** Pixel centres are the sample points of the map. A point that falls between pixel centres gets the bilinear interpolation of the (up to four) surrounding pixels, computed per RGB channel. For example, on a one-row `[black, white]` map, `fs / 4` gives `(127.5, 127.5, 127.5)`. An image one pixel tall (or wide) has a constant colour along that axis.
- **Colour averaging (D-02):** Magnitude-weighted mean RGB of the colours that the frequency bins map to. Magnitude is used both for the vertical position on the map and as the weight.
- **Colour tolerances:** `±1` per RGB channel for `ColorMapper`, and `±2` per RGB channel for overlay screenshots.
