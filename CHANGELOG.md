# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.1.0]: https://github.com/igorbispo99/ParrotIA/releases/tag/v1.1.0
[1.0.0]: https://github.com/igorbispo99/ParrotIA/releases/tag/v1.0.0
