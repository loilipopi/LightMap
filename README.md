<div align="center">

<h1>LightMap</h1>

<p><strong>Mapping Volume and Frequency to a Colour Map for a Single Colour Output</strong></p>

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=500&size=18&duration=3000&pause=1000&color=42B8D5&center=true&vCenter=true&width=550&lines=Real-time+audio+visualization;From+sound+to+colour;Visual+feedback+for+accessible+gaming" alt="LightMap: real-time audio visualization, from sound to colour, and visual feedback for accessible gaming" />

<p>
  <a href="#overview"><img alt="Overview" src="https://img.shields.io/badge/Overview-4464AD?style=for-the-badge" /></a>
  <a href="#problem-statement"><img alt="Problem Statement" src="https://img.shields.io/badge/Problem_Statement-27A8A8?style=for-the-badge" /></a>
  <a href="#specification"><img alt="Specification" src="https://img.shields.io/badge/Specification-7659BD?style=for-the-badge" /></a>
  <a href="#other-applications"><img alt="Other Applications" src="https://img.shields.io/badge/Other_Applications-397A66?style=for-the-badge" /></a>
  <a href="#group-members"><img alt="Group Members" src="https://img.shields.io/badge/Group_Members-A15D87?style=for-the-badge" /></a>
</p>

</div>

---

## Overview

LightMap is a real-time audio visualization system that converts PC audio into a single RGB colour using a two-dimensional colour map.

1. **Capture** system audio and compute its frequency spectrum using a Fast Fourier Transform (FFT).
2. **Map** frequency and normalized amplitude to RGB values on a 2D colour map.
3. **Combine** the sampled colours into one RGB output, updated continuously.
4. **Display** the output on a screen, through LEDs, or in other applications.

## Problem Statement

Many video games rely on important audio cues to inform players about actions or opportunities. This can make those games inaccessible or significantly more difficult for players who are deaf or hard of hearing.

For example, tactical shooters with bomb-defusal game modes often use distinct audio cues to indicate when an objective is planted or defused. Footsteps and certain character abilities also produce important sounds that players can use to make decisions.

This becomes even more challenging when music is mixed with these audio cues. Some games include visual cues alongside audio to improve accessibility; however, these features, particularly in competitive games, are often limited and may not communicate as much information as the audio itself.

## Specification

### Solution

LightMap aims to capture PC audio and process it using an FFT to generate a **volume-versus-frequency spectrum**. In real time, the frequency and amplitude values are mapped onto a **2D colour map**, with each detected peak corresponding to a colour. The sampled colours are then combined into **one RGB colour** that can be displayed through a screen overlay or an external light.

<p align="center">
  <img src="https://github.com/user-attachments/assets/58797190-01c4-4eaa-9415-030f20fd47b4" width="860" alt="LightMap frequency-and-volume colour mapping diagram" />
</p>

Users could also create custom colour maps for different games and scenarios. Ideally, creating these maps would be straightforward, but simplifying that process is **outside the scope of this project**.

### Example

In video games like *VALORANT*, an objective emits a periodic sound that becomes faster as its timer approaches the end. Players who cannot hear this sound may have difficulty judging how much time remains. The intended use of LightMap is to convert this audio information into a colour-based visual output, giving players another way to receive feedback.

## Other Applications

LightMap can visualize game audio to provide additional feedback for players who are deaf or hard of hearing. **The initial RGB output represents the overall audio spectrum; recognizing specific sounds would require further processing.**

Other potential applications include:

- Music-reactive lighting
- Desktop audio visualizations
- RGB device integration

## Group Members

[Joe Meritt](https://github.com/loilipopi) - Project Manager\
Robert Hoang - Designer\
[Lucas Lu](https://github.com/l-lu2007) - Developer\
[Kevin Wu](https://github.com/isnxnet) - Developer\
[Taj Sangra](https://github.com/tajsangra) - Developer

---

<div align="center">

<a href="https://github.com/loilipopi/LightMap/tree/main"><strong>LightMap main branch</strong></a>
