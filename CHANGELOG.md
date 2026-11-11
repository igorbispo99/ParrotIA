# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-11-11

### Added
- Self-contained Windows x64 installer with a per-user setup wizard, desktop and
  Start menu shortcuts, a branded parrot icon, and clean Explorer unregistration
  on uninstall. Python and FFmpeg do not need separate installation.
- Self-contained Linux x86-64 `.deb` and `.rpm` installers with application-menu
  entries and a parrot icon. Package checks install, run, and uninstall the app in
  clean Ubuntu and Fedora containers before release.
- **Transcribe on Parrot** Explorer action for supported audio/video extensions,
  including multiple selections collected into a single sequential queue and
  progress window. UTF-8 text saves beside each source without overwriting
  existing files. Per-file failures and cancellation are supported.
- Platform build scripts, shared PyInstaller packaging, frozen-app smoke tests
  (audio decoding, ONNX, Tk), and `.exe` / `.deb` / `.rpm` artifacts on releases.
- Regression tests for Explorer request concurrency, process ownership,
  collision-safe filenames, cancellation, and resilient batch processing.

### Changed
- Packaged GUI windows use the same parrot icon as the installer and shortcuts.
- Installer build constrains PyAV to versions compatible with faster-whisper's
  audio decoder, and uses CustomTkinter 5 for the existing GUI.

## [1.2.0] - 2026-06-08

### Added
- Model download detection: `Transcriber.is_model_cached()` checks the local
  HuggingFace cache so the app can tell whether a model needs to be downloaded.
- `MODEL_SIZES` and `_MODEL_REPOS` constants mapping each model name to its
  approximate download size and HuggingFace repo ID.
- GUI shows an indeterminate progress bar with a descriptive "📥 Downloading…"
  status message during first-time model downloads; switches to normal
  determinate progress once loading begins.
- Full pytest test suite (`tests/`) covering transcriber, formats, CLI,
  benchmark, public API surface, and GUI (auto-skipped on headless CI).
- CI workflow (`.github/workflows/ci.yml`) running tests on Python 3.9–3.12
  across Linux, Windows, and macOS, plus ruff lint/format checks and a wheel
  install smoke-test.
- `[dev]` optional dependency group (`pytest`, `pytest-cov`) in `pyproject.toml`.
- pytest configuration block in `pyproject.toml` (`[tool.pytest.ini_options]`).

### Changed
- Release workflow now delegates build, test, and lint to the reusable CI
  workflow instead of an inline build job, ensuring no release ships without
  passing CI.

## [1.1.0] - 2026-06-06

### Changed
- Reskinned the GUI with a parrot-themed visual identity drawn from the project
  banner: a branded "ParrotIA" hero header with logo, two-tone wordmark and
  feature badges (Offline / No Internet / Fast & Easy / Powered by Whisper).
- Sections are now rounded cards with emoji headings, and controls use a
  cohesive palette (green primary action, blue inputs, coral cancel, teal
  accents) that adapts to light and dark mode.

### Added
- Optional PyPI publishing job in the release workflow (via Trusted Publishing).

## [1.0.0] - 2026-06-05

First packaged release.

### Added
- Installable Python package (`pip install parrotia`) using a `src/` layout.
- `parrotia` console command (headless CLI) and `parrotia-gui` GUI launcher,
  registered as entry points.
- `python -m parrotia` runs the CLI; `python -m parrotia.app` runs the GUI.
- Public API surface re-exported from the top-level `parrotia` package
  (`Transcriber`, `WRITERS`, model/format constants, result dataclasses).
- `parrotia[cuda]` optional dependency group for NVIDIA GPU acceleration.
- GitHub Actions release workflow that builds the sdist + wheel and publishes a
  GitHub Release on every `v*` tag.

### Changed
- Source modules moved under the `parrotia` package; imports are now
  package-relative.
- Launchers (`run.bat`, `run.sh`) updated to run the package from source.

[1.2.0]: https://github.com/igorbispo99/ParrotIA/releases/tag/v1.2.0
[1.3.0]: https://github.com/igorbispo99/ParrotIA/releases/tag/v1.3.0
[1.1.0]: https://github.com/igorbispo99/ParrotIA/releases/tag/v1.1.0
[1.0.0]: https://github.com/igorbispo99/ParrotIA/releases/tag/v1.0.0
