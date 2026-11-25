# Dependency licenses

The runtime and development dependencies below permit use in LightMap. LightMap's MIT license covers project-owned code and assets. Each dependency keeps its own license when installed or redistributed.

## Desktop runtime

| Component | Role | License and upstream terms |
| --- | --- | --- |
| CPython and Tkinter | Interpreter, standard library and GUI bindings | [Python Software Foundation license and bundled notices](https://docs.python.org/3.14/license.html) |
| Tcl/Tk | Native GUI toolkit supplied with Python | [Tcl/Tk license](https://www.tcl-lang.org/software/tcltk/license.html) |
| Pillow | Colour-map image decoding | [MIT-CMU and wheel-specific bundled notices](https://github.com/python-pillow/Pillow/blob/main/LICENSE) |
| PyAudioWPatch | Windows playback loopback | [Apache-2.0 for the fork](https://github.com/s0d3s/PyAudioWPatch/blob/master/LICENSE.txt). It retains [PyAudio's MIT notice](https://github.com/s0d3s/PyAudioWPatch/blob/master/src/pyaudiowpatch/__init__.py) and bundles [PortAudio under an MIT-style license](https://github.com/s0d3s/PyAudioWPatch/blob/master/portaudio_v19/LICENSE.txt). |
| WASAPI, User32, GDI32 | Windows audio and overlay APIs | Provided by Windows and used through the operating system. LightMap installs no copies of these system components. |

The installed Windows CPython 3.12 wheels inspected for this audit were Pillow 13.0.0 and PyAudioWPatch 0.2.12.9. [Third-party notices](THIRD_PARTY_LICENSES.txt) include the Pillow wheel's codec notices and the audio wrapper's fork and upstream notices. For a packaged release, retain the complete license files and any applicable notices for the exact wheels and native libraries actually shipped. Apache-2.0 redistribution includes supplying the license and retaining applicable attribution and `NOTICE` material.

## Tests and automation

| Component | Role | License and upstream terms |
| --- | --- | --- |
| pytest | Tests | [MIT](https://github.com/pytest-dev/pytest/blob/main/LICENSE) |
| NumPy | Independent FFT reference in tests | [BSD-3-Clause for NumPy, with separate notices for libraries bundled in wheels](https://numpy.org/doc/stable/license.html) |
| pytest-cov | Coverage plugin | [MIT](https://github.com/pytest-dev/pytest-cov/blob/master/LICENSE) |
| coverage.py | Transitive coverage engine | [Apache-2.0](https://github.com/coveragepy/coveragepy/blob/main/LICENSE.txt) |
| actions/checkout and actions/setup-python | GitHub Actions setup | [MIT](https://github.com/actions/checkout/blob/main/LICENSE) and [MIT](https://github.com/actions/setup-python/blob/main/LICENSE) |
| pip | Installation | [MIT, with separate notices for pip's vendored packages](https://github.com/pypa/pip/blob/main/LICENSE.txt) |
| Xvfb and xauth | CI display and authentication | [X.Org license notices](https://www.x.org/releases/current/doc/xorg-docs/License.html) and [xauth source notices](https://gitlab.freedesktop.org/xorg/app/xauth) |

The double-click launcher creates a fresh local environment. This checkout also contains previously tracked `.venv` directories, including package binaries and pip's vendored dependencies. Exclude generated environments from release archives. Redistributing those directories or a frozen app requires a separate check of everything in that bundle. The installed packages carry their own metadata and notices.
