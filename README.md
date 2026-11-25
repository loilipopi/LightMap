<div align="center">

<h1>LightMap</h1>

<p><strong>Mapping Volume and Frequency to a Colour Map for a Single Colour Output</strong></p>

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=500&size=18&duration=3000&pause=1000&color=42B8D5&center=true&vCenter=true&width=550&lines=Real-time+audio+visualization;From+sound+to+colour;Visual+feedback+for+accessible+gaming" alt="LightMap: real-time audio visualization, from sound to colour, and visual feedback for accessible gaming" />

<p>
  <a href="#overview"><img alt="Overview" src="https://img.shields.io/badge/Overview-4464AD?style=for-the-badge" /></a>
  <a href="#run-lightmap"><img alt="Start LightMap" src="https://img.shields.io/badge/Run_LightMap-397A66?style=for-the-badge" /></a>
  <a href="#problem-statement"><img alt="Problem Statement" src="https://img.shields.io/badge/Problem_Statement-27A8A8?style=for-the-badge" /></a>
  <a href="#specification"><img alt="Specification" src="https://img.shields.io/badge/Specification-7659BD?style=for-the-badge" /></a>
  <a href="#group-members"><img alt="Group Members" src="https://img.shields.io/badge/Group_Members-A15D87?style=for-the-badge" /></a>
  <a href="#license"><img alt="Licenses" src="https://img.shields.io/badge/Licenses-C18A36?style=for-the-badge" /></a>
</p>

</div>

---

## Overview

LightMap is a real-time audio visualization system that converts PC audio into a single RGB colour using a two-dimensional colour map.

1. **Capture** system audio and compute its frequency spectrum using a Fast Fourier Transform (FFT).
2. **Map** each frequency bin to an RGB value on a 2D colour map, with frequency on the horizontal axis and magnitude on the vertical axis.
3. **Combine** the sampled colours into one RGB output, updated continuously.
4. **Display** the output on a screen, through LEDs, or in other applications.

## Start LightMap

### Run LightMap With cmd File

Use Windows 10 or 11 and 64-bit Python 3.12–3.14 with Tkinter. Double-click **LightMap.cmd** in File Explorer. The first launch creates a local environment and downloads the app's dependencies. Later launches use that environment and open the control window directly.

Use Windows PowerShell if the cmd file does not work.

### Run LightMap Using Terminal

Use Windows 10 or 11 and 64-bit Python 3.12–3.14 with Tkinter. From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\src\requirements.txt
cd .\src
..\.venv\Scripts\python.exe -m lightmap
```

Use `--map ember` or `--map ocean` to change the default `spectrum` palette. To use your own image, pass its path with `--map "C:\path\to\my-map.png"`. The image runs from low to high frequency left to right and from loud to quiet top to bottom. For example:

```powershell
..\.venv\Scripts\python.exe -m lightmap --map ember
```

### Settings

1. Click **Start**, enable **Show overlay**, and play audio through the default Windows output. **Stop** releases capture. Closing the app also closes the overlay.
2. Choose **Spectrum**, **Ember**, or **Ocean** under **Colour map**. **Import image…** opens a local image as a custom map. Frequency increases from left to right, and loudness increases from bottom to top.
3. Under **Colour transitions**, set **Fade in (ms)** for louder audio and **Fade out (ms)** for quieter audio or silence, then click **Apply timings**. Set either field to **0** for an immediate change in that direction. The default is **35 ms** in each direction. These are smoothing time constants, so about two-thirds of a change happens in the time entered. **Smooth colour changes** turns the effect on or off without clearing your timings.
4. Choose **Bar**, **Circle**, **Rectangle**, **Triangle**, **Diamond**, or **Hexagon**. Set the bar thickness, circle radius, or the floating shape's dimensions and rotation. Positive angles rotate clockwise. Drag the shape on the screen diagram to place it on the primary display. Bars snap to an edge. Use **Preview on desktop** to check the result without audio, or enter the position and opacity directly and click **Apply layout**.
5. Under **Audio tuning**, use the live **Input peak** meter and its orange marker to set the **Noise floor**. Lower values let quieter sounds through. Choose a **Quiet colour** for silence or when no enabled band clears the floor. Set how strongly the low, mid and high bands contribute to the colour, then click **Apply tuning**. **100%** keeps the normal weight and **0%** mutes a band.

LightMap remembers the palette, overlay visibility and layout, smoothing and audio tuning. On Windows, these are saved in `%LOCALAPPDATA%\LightMap\settings.json`. Capture starts when you press **Start**. If a saved custom image has moved, LightMap opens with **Spectrum** and lets you select the image again.

## Problem Statement

Many video games rely on important audio cues to inform players about actions or opportunities. This can make those games inaccessible or significantly more difficult for players who are deaf or hard of hearing.

For example, tactical shooters with bomb-defusal game modes often use distinct audio cues to indicate when an objective is planted or defused. Footsteps and certain character abilities also produce important sounds that players can use to make decisions.

This becomes even more challenging when music is mixed with these audio cues. Some games include visual cues alongside audio to improve accessibility; however, these features, particularly in competitive games, are often limited and may not communicate as much information as the audio itself.

## Specification

### Solution

LightMap aims to capture PC audio and process it using an FFT to generate a **volume-versus-frequency spectrum**. In real time, each frequency bin is placed on a **2D colour map** (frequency on a logarithmic horizontal axis, loudness in decibels on the vertical axis), and the colour at that point is sampled. Bins below a noise floor are ignored, and the sampled colours are combined, with louder bins counting for more, into **one RGB colour** that can be displayed through a screen overlay or an external light.

<p align="center">
  <img src="https://github.com/user-attachments/assets/58797190-01c4-4eaa-9415-030f20fd47b4" width="860" alt="LightMap frequency-and-volume colour mapping diagram" />
</p>

Users could also create custom colour maps for different games and scenarios. Ideally, creating these maps would be straightforward, but simplifying that process is **outside the scope of this project**.

### Example

In video games like *VALORANT*, an objective emits a periodic sound that becomes faster as its timer approaches the end. Players who cannot hear this sound may have difficulty judging how much time remains. The intended use of LightMap is to convert this audio information into a colour-based visual output, giving players another way to receive feedback.

## Recommended Game Settings

For games, use windowed or borderless windowed mode so the Windows desktop overlay can appear above the game.

For the best experience with LightMap, we recommend adjusting the in-game audio settings to minimize
unnecessary sounds such as background music, agent voice lines, and voice chat, while preserving important
gameplay audio cues.

Using *Valorant* as an example. Navigate to **Settings → Audio** and apply the following settings:

| Setting | Recommended Value |
|---|---|
| Overall Volume | 100% |
| Sound Effects Volume | 100% |
| Voice-over Volume | 0% |
| All Music Overall Volume | Disabled |
| Party Voice Chat | Off |
| Team Voice Chat | Off |

Even with the recommended configuration, VALORANT does not provide individual volume controls for every sound effect.

Unfortunately, you cannot completely eliminate these category through VALORANT's settings alone.
- Your own footsteps
- Your own gunshots
- Environmental ambience
- Weapon skin effects
- UI and notification sounds

We also recommend muting other desktop applications, such as Discord, Spotify, and web browsers, since LightMap captures system audio.

## Other Applications

LightMap can visualize game audio to provide additional feedback for players who are deaf or hard of hearing. **The initial RGB output represents the overall audio spectrum; recognizing specific sounds would require further processing.**

Other potential applications include:

- Music-reactive lighting
- Desktop audio visualizations
- RGB device integration

## Group Members

[Joe Meritt](https://github.com/loilipopi) - Project Manager\
[Robert Hoang](https://github.com/RobertHob1234) - Designer\
[Lucas Lu](https://github.com/l-lu2007) - Developer\
[Kevin Wu](https://github.com/isnxnet) - Developer\
[Taj Sangra](https://github.com/tajsangra) - Developer

## License

LightMap is licensed under the MIT License. See [LICENSE](LICENSE) for details.

Third-party dependencies retain their own licenses. See [DEPENDENCY_LICENSES.md](DEPENDENCY_LICENSES.md) and [THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt).

---

<div align="center">

<a href="https://github.com/loilipopi/LightMap/tree/main"><strong>LightMap main branch</strong></a>
