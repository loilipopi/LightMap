<!-- TODO before publishing: confirm every item in section 0 of verification_checklist.md with the team, and make sure both files sit in the same folder of the repo so the links below work. Delete this comment afterwards. -->

#### 5. How will you verify that you've met your requirements?

This is our acceptance testing plan. The exact tests, their steps and what counts as each one passing are in our [verification checklist](verification_checklist.md), organised by component and who is responsible. This page explains the approach, why we chose it, and which requirement is checked by which method and which part of the checklist.

We will use three main methods:

- **Automated test (A):** runs test cases in code using fake or mock components
- **Manual test (M):** needs the real audio capture or a real screen. Should attach evidence (screenshot or short note) to the GitHub Issue
- **Inspection (I):** the team reads the design against a checklist. Used for properties that tests cannot observe.

**Every requirement has at least one test or inspection.**
| Component | Tests and pass criteria | Requirements verified |
| --- | --- | --- |
| AppModel | [Checklist: AppModel](verification_checklist.md#appmodel-kevin-backup-lucas-due-18th) | CA-06, D-01, D-03, D-04 (state handling) |
| AudioCapture | [Checklist: AudioCapture](verification_checklist.md#audiocapture-robert-backup-joe-due-18th) | CA-01 to CA-06, CA-08 |
| ControlView | [Checklist: ControlView](verification_checklist.md#controlview-robert-backup-lucas-due-18th) | CA-06 |
| OverlayView | [Checklist: OverlayView](verification_checklist.md#overlayview-lucas-backup-robert-due-19th) | D-01, D-03, D-04, D-05 |
| AppController | [Checklist: AppController](verification_checklist.md#appcontroller-kevin-backup-joe-due-20th) | CA-03, CA-05 to CA-08, D-03 to D-05 |
| FrequencyAnalyser | [Checklist: FrequencyAnalyser](verification_checklist.md#frequencyanalyser-joe-backup-taj-due-20th) | FFT-01 to FFT-05 |
| ColorMapper | [Checklist: ColorMapper](verification_checklist.md#colormapper-taj-backup-kevin-due-22nd) | CM-01 to CM-03, D-02 |
| Whole system | [Checklist: Integration](verification_checklist.md#3-integration-23rd-to-26th) | CA-01, FFT-04, CM-02, D-01, D-02 end to end |
| AppModel design | [Checklist: Inspection](verification_checklist.md#2-appmodel-design-inspection-within-one-day-of-appmodel-being-finished) | Design properties behind CA-06, CM-03, D-01, CA-07, D-03 |

### Main tests outlined in requirements 

##### Capturing Audio

| Req | Method | What we check | Exact tests |
| --- | --- | --- | --- |
| CA-01 | M | Captured audio matches Audacity's (Windows WASAPI loopback) recording of the same playback, on more than one output device. | AudioCapture |
| CA-02 | A | Chunks are the same size (`t = N / fs`, `N = 1024` samples), in order, with no gaps or overlaps. | AudioCapture |
| CA-03 | A and M | No chunks are delivered after Stop. | AudioCapture, AppController |
| CA-04 | M and I | Playback is not degraded by capture (verified with Audacity WASAPI loopback), and the device is not opened exclusively. | AudioCapture |
| CA-05 | A and M | Start, Stop, Start repeated 10 times works without leaking threads or handles. | AudioCapture, AppController |
| CA-06 | A and M | The displayed status matches the model's Stopped, Active or Error state, including injected errors and an unplugged device. | AppModel, ControlView, AudioCapture, AppController |
| CA-07 | A | Pressing Start repeatedly never opens more than one session. | AppController |
| CA-08 | A and M | Capture resources are released when the application closes. | AudioCapture, AppController |

**Justification:** Everything that depends on the real Windows/OS audio stack (CA-01, CA-04, and the device-removal case) needs a real device, so those are manual, using Audacity (Windows WASAPI loopback) as ground truth. Everything about the order, size and number of chunks is pure logic, so a fake source makes it deterministic and cheap to run on every push. CA-04 also gets an inspection because "not exclusive mode" is visible in the code but hard to see in a recording.

##### FFT to Analyze Audio

| Req | Method | What we check | Exact tests |
| --- | --- | --- | --- |
| FFT-01 | A | Samples are split into complete `N`-sample windows (`N = 1024`) in order, and leftover samples wait for the next window. | FrequencyAnalyser |
| FFT-02 | A | The periodic Hann window (`0.5 * (1 - cos(2πn / N))`) is really applied (all-ones input and a bin-centred sine give the expected magnitudes). | FrequencyAnalyser |
| FFT-03 | A | Each result has bins k = 0 through floor(N / 2) for even and odd N. | FrequencyAnalyser |
| FFT-04 | A | Bin frequency is k × fs / N, and known tones peak in the nearest bin. | FrequencyAnalyser |
| FFT-05 | A | The magnitude formula is correct in isolation and against a NumPy reference. | FrequencyAnalyser |

**Justification:** FFT-02 gets its own test because a plain "known frequency" test would still pass if the Hann window were missing: the peak stays in the same place and only the magnitudes change. The all-ones input exposes it because a missing window gives a very different result. The NumPy comparison covers FFT-02 through FFT-05 together on a realistic signal, while the unit tests pinpoint which requirement failed when something breaks. Testing starts with 1 to 2 clean tones, then mixes, then game audio, so a bug is found in the simplest input that triggers it. All of it is automated because the stage is deterministic: the same samples always give the same bins.

##### Color Mapping

| Req | Method | What we check | Exact tests |
| --- | --- | --- | --- |
| CM-01 | A | Every bin, including the first and last, influences the output colour. | ColorMapper |
| CM-02 | A | 2D mapping onto the colour map (frequency horizontal: `0 Hz` = first column, `fs / 2` = last column; magnitude vertical: `0` = bottom row, `max_magnitude` = top row; clamped at the edges; bilinear between pixels) matches hand-computed colours within ±1 per RGB channel. | ColorMapper |
| CM-03 | I and A | Enough templates are provided and each one loads and produces a valid colour. | ColorMapper |

**Justification:** The mapper is a pure function from bins and a map to a colour, so automated tests with hand-computed answers fit well. We start with black and white because the correct answer is obvious by hand, then gradients, then custom maps. CM-03 is partly an inspection because "multiple templates are provided" is a statement about what ships, not about behaviour.

##### Display

| Req | Method | What we check | Exact tests |
| --- | --- | --- | --- |
| D-01 | M and A | The overlay shows the latest colour it was given (real screen pixels within ±2 per RGB channel, and last-colour-wins with a mock view). | OverlayView, AppModel |
| D-02 | A | The displayed colour equals the hand-computed magnitude-weighted mean RGB over the colour map (within ±1 per RGB channel), and a uniform map gives that colour. | ColorMapper |
| D-03 | M and A | Once enabled, the overlay stays visible over other windows and a fullscreen or borderless game until disabled. | OverlayView, AppController |
| D-04 | M and A | Once disabled, the overlay stays hidden (even as colours arrive) until re-enabled, and then shows the latest colour. | OverlayView, AppController |
| D-05 | A and M | Closing the application closes the overlay and leaves no process behind. | OverlayView, AppController |

**Justification:** The overlay is the one component whose job is what appears on the screen, so a human looking at it is not enough: we sample real pixels from a screenshot so the comparison is exact (within ±2 per RGB channel). The state logic (shown, hidden, closed) is checked with a mock view so it runs on every push. D-02 is tested through the mapper because that is where the magnitude-weighted mean RGB averaging happens, and the uniform-colour map gives an answer that does not depend on the formula, which makes a good sanity check.

##### AppController tests

AppController owns most of the behaviour behind CA-03, CA-05 to CA-08 and D-03 to D-05, so it gets its own automated test suite, listed scenario by scenario in the [AppController checklist](verification_checklist.md#appcontroller-kevin-backup-joe-due-20th). It runs against a real AppModel with a mock AudioCapture, ControlView and OverlayView.

**Justification:** The controller's job is routing and coordination. Test cases let us check exactly which calls it makes and in what order, and we can inject failures that are hard to produce on real hardware.

##### AppModel design inspection

AppModel is inspected rather than only tested because every other component depends on it, and design flaws in it get more expensive to fix with each module we build. We inspect it against the five SOLID principles (SRP, OCP, LSP, ISP, DIP) and against a rule that status can only be Stopped, Active or Error (CA-06). We also apply the interface-related checks to the interfaces AppController and the views use to reach the model, since those principles show up at component boundaries. The item-by-item list, with what each principle means for AppModel and the requirement it protects, is [section 2 of the checklist](verification_checklist.md#2-appmodel-design-inspection-within-one-day-of-appmodel-being-finished).

**How we analyze the code:** Each of the five team members works through the checklist alone, ticking each item or writing the file and line that breaks it. We then hold a 20-minute call to compare findings. The PM records the outcome in the GitHub Issue. **It passes when** every item is ticked by every member, or each problem has been fixed and the affected item re-checked by the person who raised it.

**Justification:** Reading the code individually first stops one strong opinion from shaping everyone else's review, and the call settles disagreements while the module is still small.

##### How verification fits into our process

| When | What happens | Who |
| --- | --- | --- |
| Before opening a pull request | The owner runs their component's tests locally. Manual tests are run now, and the evidence (screenshot or note) is posted in the Issue. | Component owner |
| On every push and pull request | The automated tests run through GitHub Actions. A pull request cannot move to Done while any of them fail. | Automatic |
| Before merging | One other team member (the backup owner, listed in the resilience section) reviews the code and the test evidence, using the [pull request gate](verification_checklist.md#4-gate-for-every-pull-request). | Backup owner |
| After every merge to main | The full automated suite runs again so a merge that breaks another component is caught immediately. A failing main is fixed or the merge reverted the same day. | Automatic |
| Within one day of AppModel being finished | The AppModel design inspection described above. | Whole team, PM schedules |
| Integration window, 23rd to 26th | The [end-to-end tests](verification_checklist.md#3-integration-23rd-to-26th): play a known tone through the whole chain and compare the overlay pixel to the hand-computed colour, then run game audio. | Whole team |
| Throughout | A requirement is ticked in the [requirement sign-off](verification_checklist.md#5-requirement-sign-off) only when every test listed for it passes. The PM reviews the sign-off list at each weekly meeting. | PM |

**Justification:** Automated tests run on every push because they are cheap, and a regression is easiest to fix right after the change that caused it. Manual tests run before review so reviewers see the evidence instead of re-running them. Each owner writes the tests for their own component and the backup owner reviews them, so every test gets a second set of eyes without making one person the bottleneck. The end-to-end test happens in the integration window because it needs all components finished, and it checks the connections between them that component tests cannot. Keeping the tests in one checklist means the team ticks off one list while this page records the reasoning, so the two cannot drift apart on what a test does.
