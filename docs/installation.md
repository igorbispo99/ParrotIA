# Installation

[Documentation](README.md) · [Project overview](../README.md)

## Requirements

- **Windows installer:** 64-bit Windows 10 (1809 or later) or Windows 11. Python and FFmpeg are included; models download on first use.
- **macOS app:** macOS 14 Sonoma or later, Apple Silicon or Intel (separate downloads). Models download on first use.
- **Linux installers:** x86-64 Linux with glibc 2.35 or newer (Ubuntu 22.04+, Debian 12+, current Fedora, or RHEL 10+), and an X11/XWayland desktop.
- **Install from Python/source:** Python 3.9 or later and pip.

## Windows installer (recommended)

Download `ParrotIA-<version>-windows-x64-setup.exe` from
[Releases](https://github.com/igorbispo99/ParrotIA/releases/latest). Run it and follow
the setup wizard. The installer
works for your Windows account without administrator access. It creates a Start
menu shortcut and offers a desktop shortcut and Explorer integration, both
enabled by default. Launch **ParrotIA** from either shortcut.

The installer offers **Transcribe on Parrot** in Explorer’s right-click menu.
See the [Explorer guide](usage.md#windows-explorer-action) for queue behavior,
safe output naming, and Windows 11 menu details.

The installer bundles the CPU inference runtime and all audio codecs required by
PyAV. CUDA runtime wheels and Whisper models are not bundled. The first use of
the default model downloads approximately 1.6 GB; subsequent runs use the local
model cache. Uninstalling through Windows Settings removes the app, shortcuts,
and its Explorer entries, while preserving your transcripts and downloaded models.

## macOS app (recommended)

Download the DMG matching your Mac from
[Releases](https://github.com/igorbispo99/ParrotIA/releases/latest):

- **Apple Silicon (M1 or newer):** `ParrotIA-<version>-macos-arm64.dmg`
- **Intel:** `ParrotIA-<version>-macos-x86_64.dmg`

Open the disk image, drag **ParrotIA** to **Applications**, eject the image, and
launch ParrotIA from Applications. Python, Tk, the inference engine and media
codecs are included; Homebrew and FFmpeg are unnecessary. Leave **Device → auto**
to use Metal on Apple Silicon or CPU on Intel. Select **cpu** to disable GPU use.
The first model download needs internet; subsequent transcription runs offline.
`large-v3-turbo-q5_0` offers a smaller download (about 575 MB).

Builds without a Developer ID signature and notarization may require opening
**System Settings → Privacy & Security → Open Anyway** after the first launch
attempt. Only approve builds from a source you trust. Release maintainers can
produce signed, notarized DMGs using the [macOS build options](building.md#build-the-macos-app).

To uninstall, move ParrotIA from Applications to the Trash. Transcripts and the
model cache in `~/Library/Application Support/parrotia/models` are preserved.

## Linux installers

Download the latest `.deb` or `.rpm` from
[Releases](https://github.com/igorbispo99/ParrotIA/releases/latest). Install it with your
distribution's package manager so desktop-library dependencies are resolved
(replace these example filenames with the versions you downloaded):

```bash
# Debian / Ubuntu
sudo apt install ./parrotia_1.5.2_amd64.deb
# Fedora / compatible RPM distributions
sudo dnf install ./parrotia-1.5.2-1.x86_64.rpm
```

Open **ParrotIA** from the applications menu, or run `parrotia-gui`. Both packages
include Python, the inference engine, audio codecs, and a parrot icon. Models
download on first use. Use the GUI to select files/folders and output formats;
the Explorer right-click action is specific to Windows.

Remove the app with `sudo apt remove parrotia` or `sudo dnf remove parrotia`.
Transcripts and the model cache in your home folder are preserved.

## Homebrew (macOS)

Add the ParrotIA repository as a custom tap, then install the app:

```bash
brew tap igorbispo99/parrotia https://github.com/igorbispo99/ParrotIA
# If Homebrew requires explicit trust (Homebrew 7+):
brew trust --cask igorbispo99/parrotia/parrotia
brew install --cask igorbispo99/parrotia/parrotia
```

Homebrew selects the Apple Silicon or Intel DMG and checks its SHA-256 before
installing. Launch **ParrotIA** from Applications. Upgrade with
`brew update && brew upgrade --cask parrotia`; remove with
`brew uninstall --cask parrotia`. The model cache and transcripts are preserved.
The same Gatekeeper requirements as the DMG apply to unnotarized builds.

## Python installation

Install the package (provides the `parrotia` and `parrotia-gui` commands):

```bash
python3 -m pip install parrotia
```

Or install from a checkout of this repository:

```bash
pip install .
# For development (editable install):
pip install -e .
```

> Prefer not to install? You can still run straight from the source tree with
> `pip install -r requirements.txt` and the [source launchers](usage.md#gui).

On macOS, use Python **3.10 or newer** for the whisper.cpp/Metal backend (a
native ARM Python on Apple Silicon). A source install also needs Python's Tk
support; the macOS app above includes it. Python 3.9 keeps the faster-whisper
CPU backend. Intel Python installations use faster-whisper on the CPU. The DMG bundles
whisper.cpp on both architectures. To build whisper.cpp yourself, follow the
[static runtime build instructions](building.md#build-the-macos-app); use the DMG to avoid build tools.

Models download on first use and are cached for offline use. Downloads range from
about 75 MB to 3.1 GB; the default `large-v3-turbo` is about 1.6 GB. See the
[model guide](models.md) for smaller options.

## GPU acceleration

Apple Silicon uses Metal automatically in the macOS app. For NVIDIA CUDA setup,
backend overrides, and model cache locations, see [Models and acceleration](models.md).

## Next step

Follow the [usage guide](usage.md) to transcribe your first file or run a batch.
