# Building installers

[Documentation](README.md) · [Project overview](../README.md)

Run these commands from the repository root. For development setup and release
publication, see [Development and releases](development.md).

## Build the Windows installer locally

Use 64-bit Python 3.12 and [Inno Setup 6 or newer](https://jrsoftware.org/isdl.php)
on Windows. From the repository root:

```powershell
.\packaging\windows\build.ps1
# If ISCC.exe is not in a standard install location:
.\packaging\windows\build.ps1 -Iscc "C:\path\to\ISCC.exe"
# Build just the standalone folder, without an installer compiler:
.\packaging\windows\build.ps1 -BundleOnly
```

The script creates an isolated `.venv-windows` environment. PyInstaller bundles
the application, Python, Tk, fonts, native inference libraries, audio codecs, and
the Silero speech detector. The build smoke-tests the **frozen executable** by
decoding a small WAV, loading Silero ONNX, and creating the GUI; no Whisper model
download is required. Inno Setup then writes the single distributable installer
to `dist/installer/`. Keep the whole `dist/ParrotIA/` folder together when using
the portable build.

The **Windows installer** GitHub Actions workflow also supports manual runs and
uploads the installer as an artifact. Releases wait for it and attach the EXE
alongside the Python distributions. Packaging sources live in
[`packaging/windows/`](../packaging/windows/); media associations are generated from
the engine's `SUPPORTED_EXTENSIONS` so the supported file lists stay aligned.

The CI build also installs into a temporary test folder, verifies both shortcut
targets and every Explorer registration, runs the installed executable's smoke
test, and uninstalls to verify cleanup. Run the same check locally with
`packaging/windows/test-installer.ps1 -Installer <path-to-setup.exe>` only when
ParrotIA is not already installed. It refuses to replace an existing installation,
shortcut, or Explorer entry. Managed Windows policies such as Controlled Folder
Access can block this check; the script does not change security settings.
For diagnosing policies that track the installer's temporary helper path, compile
`installer.iss` with the additional Inno preprocessor definition
`/DStableValidation=1`. This creates a diagnostic installer at the fixed path
`dist/installer-check/ParrotIA-InstallerCheck.exe`, with companion `.bin` files
that must stay beside it. It uses Inno's `UseSetupLdr=no` debug mode; the release
installer is still a single EXE. Any Windows allowance is a manual user action.

## Build the macOS app

Build on each target architecture using native Python 3.12 with Tk support and
Xcode Command Line Tools (macOS 14 or newer):

```bash
python3.12 -m venv .venv-macos
source .venv-macos/bin/activate
# Compile a portable runtime with embedded Metal kernels.
CMAKE_ARGS="-DBUILD_SHARED_LIBS=OFF -DCMAKE_OSX_ARCHITECTURES=$(uname -m) -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON -DGGML_NATIVE=OFF" \
  MACOSX_DEPLOYMENT_TARGET=14.0 pip install --no-binary pywhispercpp 'pywhispercpp==1.5.1'
pip install '.[macos-build]'
python packaging/macos/build.py
python packaging/macos/test_installer.py
```

For an Intel CPU build, use `-DGGML_METAL=OFF` instead.

The build produces `dist/ParrotIA.app` and an architecture-specific DMG under
`dist/installer/`. It smoke-tests native imports, audio decoding and GUI startup
without a model download, and requires a Metal-enabled runtime for ARM builds.
For an additional frozen CPU/Metal inference check, set `PARROTIA_SMOKE_MODEL`
to an existing GGML model file before building; optionally set
`PARROTIA_SMOKE_AUDIO` to a short English speech recording. Results are included
in `build/macos/smoke-test.json`.

To exercise the actual GUI worker, put a downloaded `tiny` GGML model in
`PARROTIA_MODELS_DIR` and set `PARROTIA_SMOKE_MODEL_NAME=tiny` before building.
The build then tests completed transcription and quitting during decoding in
fresh frozen processes, checks GUI heartbeat gaps, and verifies worker cleanup.
CI runs these model lifecycle checks on both Mac architectures.
The installer check mounts the DMG, copies the app into a temporary folder,
ejects the image, and tests that copy. The **macOS installers** workflow builds
both architectures and releases attach both DMGs. The release also includes
a generated `parrotia.rb` Homebrew cask with hashes of those exact DMGs.
After publishing, copy that file into `Casks/parrotia.rb` on `main` and commit
it to update the tap. To regenerate locally, place both release DMGs in
`dist/installer/` and run `python packaging/macos/update_cask.py`.

For distribution without Gatekeeper overrides, sign and notarize with your own
Apple Developer ID and a `notarytool` profile already stored in Keychain:

```bash
python packaging/macos/build.py \
  --sign-identity "Developer ID Application: Your Name (TEAMID)" \
  --notary-profile "parrotia-notary"
```

This signs the app and DMG, submits the DMG to Apple, staples the ticket and
checks Gatekeeper acceptance. Without these options the app is ad-hoc signed
for local use; CI artifacts are unsigned by Developer ID and unnotarized.

Release tags can sign and notarize in CI once the Apple secrets exist, and sign
the Windows installer through SignPath. See [Code signing setup](code-signing.md).

## Build the Linux installers

Build natively on x86-64 or ARM64 Ubuntu 22.04 to keep the glibc baseline at 2.35:

```bash
sudo apt install binutils rpm python3-venv python3-tk xvfb xauth desktop-file-utils
python3 -m venv .venv-linux-arm64
. .venv-linux-arm64/bin/activate
pip install '.[linux-build]'
xvfb-run -a python packaging/linux/build.py
```

The shared [`packaging/ParrotIA.spec`](../packaging/ParrotIA.spec) and launcher build
the same self-contained desktop app on Windows and Linux. Linux packages install
under `/opt/parrotia`, with a `parrotia-gui` launcher and application-menu entry.
Outputs are `dist/installer/parrotia_<version>_amd64.deb` and
`dist/installer/parrotia-<version>-1.x86_64.rpm` on x86-64; ARM64 builds produce
`parrotia_<version>_arm64.deb` and `parrotia-<version>-1.aarch64.rpm`. Linux
installers require no separate Python installation. The **Linux installers** CI workflow verifies both
packages by installing, running the frozen app, and uninstalling on an Ubuntu
runner and in a clean Fedora container on each architecture before release.

On Apple Silicon with OrbStack, create a native build machine and run the same
commands above inside it (the repository is accessible through the shared macOS
path):

```bash
orb create -a arm64 ubuntu:22.04 parrotia-arm64
orb -m parrotia-arm64
cd /Users/<you>/path/to/ParrotIA  # use your checkout path
```

Keep the Linux virtual environment separate from macOS environments. Build on
Ubuntu 22.04 rather than a newer distribution to retain glibc 2.35 compatibility.
