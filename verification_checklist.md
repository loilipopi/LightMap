# LightMap verification checklist

Legend: **(A)** automated test, **(M)** manual test with evidence posted in the GitHub Issue, **(I)** inspection. IDs are prefixed by section: **CA** Capturing Audio, **FFT** FFT to Analyze Audio, **CM** Color Mapping, **D** Display.

## 0. Pre Components
- [ ] Make sure everyone knows how to use github and setup an actual workflow 
- [x] Window size N = 1024 and chunk time t = N / fs (one chunk = one analysis window, no overlap)
- [x] Hann form: periodic, `0.5 * (1 - cos(2πn / N))`
- [x] Colour map is 2D: frequency on the horizontal axis, magnitude on the vertical axis
- [x] Frequency axis of the colour map: 0 Hz = first column, fs / 2 = last column
- [ ] Magnitude axis of the colour map: linear, 0 = bottom row, max_magnitude = top row (proposed default max_magnitude = 0.5)
- [x] Colours between pixel centres are bilinearly interpolated
- [x] D-02 averaging formula: magnitude-weighted mean RGB of the colours the bins map to
- [ ] Minimum number of colour map templates (proposed 3)
- [x] Colour tolerances: ±1 per RGB channel for ColorMapper, ±2 per RGB channel for overlay screenshots
- [x] External audio recorder chosen for CA-01 and CA-04: Audacity (Windows WASAPI loopback)
- [ ] CI (GitHub Actions) runs the automated tests without a real audio device or screen

## 1. Component checklists

Each component is done when every box under it is ticked.

### AppModel: Kevin, due 18th

- [ ] **(A)** Status can only be Stopped, Active or Error, starts as Stopped, and cannot hold any other value (CA-06)
- [ ] **(A)** Setting a new latest colour replaces the old one (D-01)
- [ ] **(A)** The overlay enabled flag reads back what was set (D-03, D-04)
- [ ] **(I)** SOLID design inspection passed (see section 2)
- [ ] Tests pass in CI, backup owner has reviewed the pull request, Issue moved to Done

### AudioCapture: Robert, due 18th

- [ ] **(A)** CA-02: fake source outputs a ramp (sample i = i). Every chunk has exactly t × fs = N = 1024 samples and the joined chunks equal the source (no gaps, overlaps or reordering)
- [ ] **(A)** CA-03: after Stop, zero chunks are delivered for 2 seconds
- [ ] **(A)** CA-05: Start, Stop, Start x10. Chunks arrive within 1 second each time and thread/handle counts after the 10th cycle equal the 1st
- [ ] **(A)** CA-08: release is called exactly once on shutdown, with capture active and with capture stopped, and neither throws
- [ ] **(M)** CA-01: play a 440 Hz tone and compare with Audacity (Windows WASAPI loopback). Same dominant frequency (within one bin) and level within 1 dB, on two output devices. A microphone-only sound is not captured
- [ ] **(M)** CA-03: press Stop during real playback. The device is no longer open
- [ ] **(M)** CA-04: record a 5-minute track in Audacity (Windows WASAPI loopback) with capture off then on, for two tracks. No dropouts or glitches, volume within 1 dB
- [ ] **(I)** CA-04: the device is opened in shared mode, not exclusive
- [ ] **(M)** CA-06: unplug the output device mid-capture. Status becomes Error
- [ ] **(M)** CA-08: close the app during real capture. Another app can capture the device and no process remains in Task Manager
- [ ] Tests pass in CI, evidence attached to the Issue, backup owner has reviewed, Issue moved to Done

### ControlView: Robert, due 18th

- [ ] **(A)** Start and Stop controls call the controller with the right action
- [ ] **(A)** Overlay enable and disable controls call the controller with the right action
- [ ] **(A)** CA-06: the status text equals the AppModel state for Stopped, Active and Error
- [ ] **(A)** Intentional errors (mock capture throws an exception) are shown in the view
- [ ] **(A)** The coverage report shows every branch of the start/stop, overlay enable/disable and status functions is exercised
- [ ] Tests pass in CI, backup owner has reviewed, Issue moved to Done

### OverlayView: Lucas, due 19th

- [ ] **(M)** D-01: drive the overlay with a colour-cycling function and screenshot it at several points. Sampled pixels match the commanded colour within ±2 per channel
- [ ] **(A)** D-01: send two colours back to back to a mock view. The last one is shown
- [ ] **(M)** D-03: enable for 60 seconds while colours update, click other windows, and run a fullscreen or borderless game window. It stays visible
- [ ] **(A)** D-04: disabled overlay stays hidden even when new colours arrive, and re-enabling shows the latest colour (not a stale one)
- [ ] **(M)** D-04: confirm the above in a screenshot
- [ ] **(A)** D-05: shutdown records a hide or close call
- [ ] **(M)** D-05: close with the close button and with any menu exit. The overlay is gone and no process remains
- [ ] Tests pass in CI, evidence attached to the Issue, backup owner has reviewed, Issue moved to Done

### AppController: Kevin, due 20th

All **(A)**, using a real AppModel with mock AudioCapture, ControlView and OverlayView.

- [ ] Start then Stop: the mock capture gets one start then one stop, and status goes Active then Stopped (CA-03)
- [ ] Start twice, then Start x100 rapidly: the mock shows exactly one open session (CA-07)
- [ ] Start, Stop, Start: a second session opens and the first is fully released (CA-05)
- [ ] Capture throws an error: status is Error and ControlView shows it (CA-06)
- [ ] Enable overlay then disable: OverlayView gets show then hide, and AppModel's flag matches (D-03, D-04)
- [ ] Colour update while disabled, then enable: OverlayView shows the latest colour (D-04)
- [ ] Application shutdown: capture released once and overlay closed (CA-08, D-05)
- [ ] Tests pass in CI, backup owner has reviewed, Issue moved to Done

### FrequencyAnalyser: Joe, due 20th

All **(A)**. Start with 1 to 2 clean tones, then mixes, then game audio.

- [ ] FFT-01: feed 10N + (N - 1) samples in uneven chunks. Exactly 10 results exist and result i used samples iN to iN + N - 1. Feeding 1 more sample produces an 11th result. N - 1 samples alone produce none
- [ ] FFT-02: input all ones. Magnitude is 0.5 at bin 0, 0.25 at bin 1, and 0 elsewhere (periodic Hann `0.5 * (1 - cos(2πn / N))`; no Hann would give 1 at bin 0 and 0 elsewhere)
- [ ] FFT-02: input a sine of amplitude A at exactly bin 100. A/4 at bin 100, A/8 at bins 99 and 101, about 0 elsewhere (all within 1e-6)
- [ ] FFT-03: N = 8, 7 and 1024 give 5, 4 and 513 pairs (k = 0 through floor(N / 2))
- [ ] FFT-04: frequency list equals k × fs / N at 44100 Hz and 48000 Hz
- [ ] FFT-04: 1 kHz, 440 Hz, a 440 + 1000 Hz mix, and game audio each peak within half a bin width (fs / 2N) of the true frequency
- [ ] FFT-05: magnitude unit test (real = 3, imaginary = 4, N = 10 gives exactly 0.5)
- [ ] FFT-05: full output matches `abs(rfft(x * hann)) / N` (using periodic Hann) from NumPy within 1e-6 on every bin
- [ ] Tests pass in CI, backup owner has reviewed, Issue moved to Done

### ColorMapper: Taj, due 22nd

All **(A)** except CM-03's inspection. Start with black and white, then gradients, then a custom map.

- [ ] CM-02: 2-pixel black and white map (one row). 0 Hz gives the first column, fs / 2 gives the last, and fs / 4 gives the midpoint
- [ ] CM-02: 2-pixel map (one column, bottom black, top white). Magnitude 0 gives black, max_magnitude gives white, max_magnitude / 2 gives the midpoint, and magnitudes above max_magnitude give white
- [ ] CM-02: 2×2 map. A pair at fs / 4 and max_magnitude / 2 gives the mean of the four corners (bilinear)
- [ ] CM-02: gradient map and custom map match hand-computed colours within ±1 per channel
- [ ] CM-01: with a map where every position has a different colour, setting one bin at a time (every k from 0 to floor(N / 2), including both ends) changes the output from the all-zero output
- [ ] D-02: hand-computed spectra give the expected magnitude-weighted mean RGB colour within ±1 per channel
- [ ] D-02: a uniform-colour map gives that colour whatever the spectrum
- [ ] **(I)** CM-03: templates folder contains at least the agreed minimum number of maps
- [ ] CM-03: every template loads and produces a valid colour (each channel 0 to 255)
- [ ] Tests pass in CI, backup owner has reviewed, Issue moved to Done

## 2. AppModel design inspection (within one day of AppModel being finished)

Each of the five members works through the list alone first, ticking each item or writing the file and line that breaks it. Then a 20-minute call. The PM records the outcome in the Issue.

- [ ] **SRP:** AppModel only holds and updates state (capture status, settings, latest colour). No audio, FFT, colour-mapping or UI code
- [ ] **OCP:** adding a setting, status or colour map template means adding code, not editing existing methods
- [ ] **LSP:** anything implementing an AppModel interface (including our test fake) keeps the same contract. N/A if there are no interfaces
- [ ] **ISP:** views get narrow read-only interfaces (OverlayView only the latest colour, ControlView only the status)
- [ ] **DIP:** AppController and the views depend on an AppModel abstraction, and the model imports no view classes
- [ ] Status can only be one of the three CA-06 values
- [ ] ISP and DIP also checked on the interfaces AppController and the views use to reach the model
- [ ] Kevin: Issue shows each item ticked by all members, or each problem fixed and re-checked by the person who raised it

## 3. Integration, 23rd to 26th

- [ ] Full automated suite passes on main
- [ ] End-to-end **(M)**: play a known tone through the whole chain (AudioCapture, FrequencyAnalyser, ColorMapper, OverlayView). The overlay screenshot pixel matches the hand-computed colour within ±2 per RGB channel (covers CA-01, FFT-04, CM-02, D-01, D-02)
- [ ] End-to-end with game audio for at least 5 minutes: no crash, no dropout, overlay keeps updating
- [ ] Start, Stop and Start again, enable and disable the overlay, then close the app, with everything running together
- [ ] Any failure raised as a GitHub Issue, assigned to the component owner, and retested
- [ ] Functional by the 27th

## 4. Gate for every pull request

- [ ] Owner ran the component's tests locally
- [ ] Manual test evidence (screenshot or note) posted in the Issue
- [ ] GitHub Actions is green
- [ ] Backup owner reviewed the code and the evidence
- [ ] Merged to main, and the full suite passed again afterwards (if main fails, fix or revert the same day)

## 5. Requirement sign-off

Tick a requirement only when every test listed for it above passes.

**Capturing Audio**
- [ ] CA-01 (AudioCapture)
- [ ] CA-02 (AudioCapture)
- [ ] CA-03 (AudioCapture, AppController)
- [ ] CA-04 (AudioCapture)
- [ ] CA-05 (AudioCapture, AppController)
- [ ] CA-06 (AppModel, ControlView, AppController)
- [ ] CA-07 (AppController)
- [ ] CA-08 (AudioCapture, AppController)

**FFT to Analyze Audio**
- [ ] FFT-01 (FrequencyAnalyser)
- [ ] FFT-02 (FrequencyAnalyser)
- [ ] FFT-03 (FrequencyAnalyser)
- [ ] FFT-04 (FrequencyAnalyser)
- [ ] FFT-05 (FrequencyAnalyser)

**Color Mapping**
- [ ] CM-01 (ColorMapper)
- [ ] CM-02 (ColorMapper)
- [ ] CM-03 (ColorMapper)

**Display**
- [ ] D-01 (OverlayView, AppModel)
- [ ] D-02 (ColorMapper)
- [ ] D-03 (OverlayView, AppController)
- [ ] D-04 (OverlayView, AppController)
- [ ] D-05 (OverlayView, AppController)
