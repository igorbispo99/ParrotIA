# Usage

[Documentation](README.md) · [Project overview](../README.md)

## GUI

For desktop installers, launch **ParrotIA** from Applications (macOS), the Start
menu (Windows), or your applications menu (Linux). For Python installations:

```bash
parrotia-gui
# or, without installing:  python -m parrotia.app
```

Or use the platform launcher (runs from source; edit the `PYTHON` variable inside if needed):

| Platform | Launcher |
|----------|----------|
| Windows  | double-click `run.bat` |
| macOS / Linux | `chmod +x run.sh && ./run.sh` |

1. Pick a single audio/video **File…**, or a **Folder…** to transcribe every supported file inside it
2. Choose a **model**, **language**, **device**, and **output formats**
3. Click **Transcribe** — each file's outputs are saved next to it (or in a folder you choose) and previewed in the window; a batch reports overall progress and a per-file summary at the end

## Command line

```bash
parrotia "talk.mp3" --model large-v3-turbo --formats txt srt --language en
# or, without installing:  python -m parrotia "talk.mp3" ...
```

```
usage: parrotia [-h] [--backend BACKEND] [--model MODEL] [--language LANGUAGE] [--device DEVICE]
                [--compute COMPUTE] [--formats FORMAT [FORMAT ...]] [--outdir OUTDIR]
                audio

positional arguments:
  audio                 Path to the audio/video file

options:
  --backend             faster-whisper | whisper.cpp (default: detected)
  --model               Whisper model to use (default: large-v3-turbo)
  --language            Language code, e.g. en, pt (omit to auto-detect)
  --device              cpu | cuda | metal | auto (backend/platform dependent; default: auto)
  --compute             int8 | int8_float16 | float16 | float32 | auto (default: auto)
  --formats             One or more output formats: txt md srt vtt json
  --outdir              Output folder (defaults to the source file's folder)
  --benchmark           Time several models on the file and print a speed
                        comparison instead of transcribing
  --models              Models to compare in --benchmark mode (default: all)
```

## Benchmarking model speed

Compare how fast different models transcribe the same file — useful for picking the best speed/accuracy trade-off for your hardware:

```bash
parrotia "talk.mp3" --benchmark --models tiny base small large-v3-turbo
```

This loads and runs each model in turn, then prints a table reporting model **load** time, **decode** time, and **speed** — the real-time factor (seconds of audio transcribed per second of wall-clock time; higher is faster):

```
Model                 Audio     Load   Decode     Speed  Segments
-----------------------------------------------------------------
tiny                  78.8s     3.1s     6.6s      11.9x        26
base                  78.8s     9.4s     2.8s      28.0x        24
small                 78.8s     5.2s     7.1s      11.1x        25
large-v3-turbo        78.8s    12.0s     9.3s       8.5x        23

Fastest: base — 28.0x real-time (2.8s to decode 78.8s of audio)
```

Omit `--models` to benchmark every available model. The report is also written to `<file>.benchmark.txt` and `<file>.benchmark.json` next to the source (or in `--outdir`). Each model is loaded fresh so download/warm-up time is reflected honestly; a model that fails to run is recorded and the rest continue.

## Windows Explorer action

To transcribe without configuring a job, select one or more supported media files
in Explorer, right-click, and choose **Transcribe on Parrot**. On Windows 11, open
**Show more options** to find this entry. One progress window queues the files,
uses `large-v3-turbo` with automatic language/device detection, and saves a UTF-8
`.txt` beside each source. Additional selections join the same queue. A failed
file is reported in the window while the rest continue; **Cancel queue** stops
the remaining work.

Existing files are preserved: `meeting.mp4` produces `meeting.txt`, or
`meeting (1).txt`, `meeting (2).txt`, etc. if needed. Read-only folders report an
error; use the full GUI and choose a writable output folder for those files.
The classic Explorer menu supports selections of up to 100 files
([Windows selection model](https://learn.microsoft.com/en-us/windows/win32/shell/how-to-employ-the-verb-selection-model));
submit larger batches through the GUI's folder picker.

## Export formats

| Format | Extension | Description |
|--------|-----------|-------------|
| `txt`  | `.txt`    | Plain transcript, one segment per line |
| `md`   | `.md`     | Markdown document with metadata header and timestamps |
| `srt`  | `.srt`    | SubRip subtitles |
| `vtt`  | `.vtt`    | WebVTT subtitles |
| `json` | `.json`   | Structured JSON with full metadata and per-segment timings |

## Input formats

`.mp3` · `.wav` · `.m4a` · `.ogg` · `.oga` · `.opus` · `.flac` · `.aac` · `.wma` · `.mp4` · `.mkv` · `.mov` · `.avi` · `.webm`

For model selection, backend-specific device choices, and offline caching, see
[Models and acceleration](models.md).
