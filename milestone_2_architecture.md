# Milestone 2: Architecture

## Notes

The architecture follows Model–View–Controller, with separate services for audio capture, frequency analysis, and colour conversion. This is a reflection of our requirements and specifications documents so any changes to those documents must also be applied here. 

## Components

### AppModel: Model

**Responsibility:** Store capture status, processing settings, and the latest output colour.

**Location:** Client only.

**Communication:**
- AppController updates capture status, settings, and output colour.
- AppController retrieves these values to update the views.

### AppController: Controller

**Responsibility:** Handle user actions and coordinate the audio processing pipeline.

**Location:** Client only.

**Communication:**
- Receives Start, Stop, and overlay enable/disable requests from ControlView.
- Requests AudioCapture to start or stop capture.
- Receives captured audio samples and their sample rate from AudioCapture.
- Supplies samples and their sample rate to FrequencyAnalyser.
- Supplies the resulting frequency–magnitude pairs to ColourMapper.
- Updates AppModel with capture status, settings, and the latest output colour.
- Supplies capture status and error messages to ControlView.
- Supplies output colours and visibility commands to OverlayView.\
- Supplies image to ColourMapper

### ControlView: View

**Responsibility:** Display application controls, capture status, and error messages.

**Location:** Client only.

**Communication:**
- Sends Start, Stop, and overlay enable/disable requests to AppController.
- Receives capture status and error messages from AppController.

### OverlayView: View

**Responsibility:** Display the latest output colour over the game (matching the commanded colour within ±2 per RGB channel in overlay screenshots).

**Location:** Client only.

**Communication:**
- Receives an RGB colour from AppController.
- Receives show and hide commands from AppController.

### AudioCapture: Model

**Responsibility:** Capture playback audio from the computer's default output device in chunks of duration `t = N / fs` (`N = 1024` samples, one analysis window, no overlap).

**Location:** Client only.

**Communication:**
- Receives start and stop requests from AppController.
- Supplies captured samples in chronological order (chunks of `N = 1024` samples, duration `t = N / fs`) and their sample rate `fs` to AppController.
- Reports capture failures to AppController.

### FrequencyAnalyser: Model

**Responsibility:** Buffer audio samples into `N = 1024`-sample analysis windows (non-overlapping, `hop_size = N`), apply the periodic Hann window `0.5 * (1 - cos(2πn / N))`, and compute their frequency spectra using FFT.

**Location:** Client only.

**Communication:**
- Receives audio samples and their sample rate from AppController.
- Receives analysis settings, including window size (`N = 1024`) and hop size (`N = 1024`, no overlap), from AppController.
- Returns frequency–magnitude pairs for bins `k = 0` through `floor(N / 2)` for each completed analysis window to AppController.
- Receives reset requests from AppController to discard buffered samples between capture sessions.

### ColourMapper: Model

**Responsibility:** Convert frequency–magnitude pairs into colours using the predefined colour map (linear frequency axis: `0 Hz` = first pixel, `fs / 2` = last pixel) and combine them into one output colour via magnitude-weighted mean RGB (within ±1 per RGB channel).


**Location:** Client only.

**Communication:**
- Receives frequency–magnitude pairs and colour-mapping settings from AppController.
- Process image (one time) into a linear map for mapping frequency-magnitude pairs (`0 Hz` = first pixel, `fs / 2` = last pixel).
- Computes the magnitude-weighted mean RGB of the colours mapped from all frequency–magnitude pairs.
- Returns one RGB colour per analysis result to AppController (within ±1 per RGB channel).

### Code Stub Locations

All Python code stubs are located in `src/lightmap/`.

| Component | File |
|---|---|
| AppModel | `src/lightmap/app_model.py` |
| AppController | `src/lightmap/app_controller.py` |
| AudioCapture | `src/lightmap/audio_capture.py` |
| FrequencyAnalyser | `src/lightmap/audio_analyser.py` |
| ColourMapper | `src/lightmap/colour_mapper.py` |
| ControlView | `src/lightmap/control_view.py` |
| OverlayView | `src/lightmap/overlay_view.py` |

The application runs entirely on the client computer.
No remote server is required.
