## Problem
Individuals with poor hearing cant play video games that make use of important audio ques. These video games become inaccessible or significantly more difficult to play for these individuals. 

## Solution
We want to create a tool where PC audio is captured and processed with a FFT to create a Volume vs Frequency map. In real time, this will correspond to a colour map mapping each peak onto a single colour in which one singular colour is produced. This will then be outputted to either an overlay or an external light.

<img width="955" height="455" alt="image" src="https://github.com/user-attachments/assets/58797190-01c4-4eaa-9415-030f20fd47b4" />
Additionally, the user can create their own custom colour map for whatever scenario and game they want, ideally this should be easy to make but is outside the scope of this project.


For example in a game like Valorant, there is an objective emits a sound periodically which gets faster as it nears the end of the timer. Not being able to hear that sound is detrimental as can't tell how much time is left. What our software will do is take that sound convert it to a colour and output it to the user.

## Technical Specifications
- **Window size and chunk duration:** Window size `N = 1024` samples and chunk duration `t = N / fs` (where `fs` is the audio sample rate in Hz), so one chunk equals one analysis window with no overlap.
- **Hann window:** Periodic Hann window `w[n] = 0.5 * (1 - cos(2πn / N))` for `n = 0, ..., N - 1`, applied to each complete analysis window before computing the N-point FFT.
- **FFT output:** Frequency–magnitude pairs for bins `k = 0` through `floor(N / 2)`, with bin frequency `k × fs / N` Hz and magnitude `sqrt(real² + imaginary²) / N`.
- **Colour map frequency axis:** Linear mapping where `0 Hz` corresponds to the first pixel and `fs / 2` corresponds to the last pixel.
- **Colour averaging (D-02):** Magnitude-weighted mean RGB of the colours that the frequency bins map to.
- **Colour tolerances:** `±1` per RGB channel for `ColorMapper`, and `±2` per RGB channel for overlay screenshots.
