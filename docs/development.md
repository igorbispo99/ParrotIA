# Development and releases

[Documentation](README.md) · [Project overview](../README.md)

## Local setup

Use Python 3.9 or newer; Apple Silicon acceleration needs Python 3.10 or newer.
Python 3.12 is used for installer builds. A source GUI installation needs Tk.

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e '.[dev]'
parrotia-gui
```

## Checks

```bash
python -m pytest
python -m pip install ruff
ruff check src/ tests/ packaging/
ruff format --check src/ tests/ packaging/
```

GUI tests need a desktop display. On headless Linux, run them with
`xvfb-run -a python -m pytest`. Model inference and downloads are mocked in
the unit tests; audio decoding and available GUI tests use installed libraries.
Installer builds separately smoke-test the frozen app. GUI tests skip when
a display is unavailable.

## Project structure

| File | Purpose |
|------|---------|
| [`src/parrotia/app.py`](../src/parrotia/app.py) | customtkinter GUI |
| [`src/parrotia/transcriber.py`](../src/parrotia/transcriber.py) | Whisper engine (backend selection, model cache, progress callbacks, cancellation, GPU fallback) |
| [`src/parrotia/_whispercpp.py`](../src/parrotia/_whispercpp.py) | whisper.cpp backend (pinned/verified model downloads, PyAV/ffmpeg decoding) |
| [`src/parrotia/formats.py`](../src/parrotia/formats.py) | txt / md / srt / vtt / json writers |
| [`src/parrotia/cli.py`](../src/parrotia/cli.py) | Headless command-line interface |
| [`src/parrotia/benchmark.py`](../src/parrotia/benchmark.py) | Model speed benchmarking (CLI) |

## Python API

The transcription engine is UI-agnostic and importable:

```python
from parrotia import Transcriber, WRITERS

with Transcriber() as engine:
    result = engine.transcribe("talk.mp3", model="large-v3-turbo", language="en")
print(WRITERS["srt"][1](result))   # render SRT subtitles as a string
```

## Publishing a release

Tagged versions are built into a wheel, source distribution, Windows `.exe`, and
Linux `.deb` / `.rpm` installers, and macOS `.dmg` apps and published as a
[GitHub Release](https://github.com/igorbispo99/ParrotIA/releases) automatically
by the `Release` workflow. Release pages show direct download links first and
only that version's changelog section; the complete history stays in
`CHANGELOG.md`. To cut a release, bump `__version__` in
[`src/parrotia/__init__.py`](../src/parrotia/__init__.py), update
[`CHANGELOG.md`](../CHANGELOG.md), then push a matching tag (use the version you just set):

```bash
# Example for the next patch release:
git tag v1.5.3
git push origin v1.5.3
```

Each tag must have a matching `## [<version>]` entry in `CHANGELOG.md`.
`packaging/release_notes.py` extracts that section and puts links to the actual
release artifacts first; it fails if the entry is missing.

After publication, copy the generated `parrotia.rb` release asset into
`Casks/parrotia.rb` on `main` and commit it to update the Homebrew tap.
See [Building installers](building.md) for platform build and signing options.

## Contributing

Bug reports and pull requests are welcome. Include your OS, installation method,
backend, model, and steps to reproduce when reporting a problem.

See the [changelog](../CHANGELOG.md) for released changes, the
[Snap packaging guide](../snap/README.md) for the Snap build, and the
[store submission plan](store-submission-plan.md) for distribution research.
