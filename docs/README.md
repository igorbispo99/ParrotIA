# ParrotIA documentation

[Project overview](../README.md) · [Download](https://github.com/igorbispo99/ParrotIA/releases/latest) · [Report an issue](https://github.com/igorbispo99/ParrotIA/issues)

## Getting started

1. [Install ParrotIA](installation.md) for your platform.
2. [Transcribe a file or folder](usage.md#gui).
3. [Choose a model and acceleration settings](models.md).

Desktop installers include Python and media codecs. The first transcription
requires a model download; subsequent transcription can run offline.

## User guides

| I want to… | Read |
| --- | --- |
| Install, upgrade, or uninstall the app | [Installation](installation.md) |
| Install with Homebrew | [Homebrew on macOS](installation.md#homebrew-macos) |
| Install the Python package or run from source | [Python installation](installation.md#python-installation) |
| Use the desktop app or process a whole folder | [GUI](usage.md#gui) |
| Transcribe from the command line | [Command line](usage.md#command-line) |
| Right-click files in Windows Explorer | [Explorer action](usage.md#windows-explorer-action) |
| Compare transcription speed | [Benchmarking](usage.md#benchmarking-model-speed) |
| Check supported input and export formats | [Usage](usage.md#export-formats) |
| Select a model, use Metal/CUDA, or work offline | [Models and acceleration](models.md) |

## Development and distribution

- [Development and releases](development.md): setup, checks, source map, Python API, and publishing.
- [Building installers](building.md): native packages, frozen-app checks, signing, and notarization.
- [Snap packaging](../snap/README.md): Snap-specific build and verification instructions.
- [Changelog](../CHANGELOG.md): the complete release history.
- [Store submission plan](store-submission-plan.md): distribution research and planned work.
