"""Headless transcription — useful for batch jobs, scripting, and testing.

Example:
    python cli.py "talk.mp3" --model large-v3-turbo --formats txt srt --language en
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Windows consoles default to a legacy code page (cp1252) that can't encode the
# progress bar / status glyphs. Force UTF-8 and never let printing crash a run.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

import formats
from transcriber import (
    AVAILABLE_MODELS,
    COMPUTE_TYPES,
    DEFAULT_MODEL,
    DEVICES,
    LANGUAGES,
    Transcriber,
)


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local Whisper transcription.")
    parser.add_argument("audio", help="Path to the audio/video file.")
    parser.add_argument("--model", default=DEFAULT_MODEL, choices=AVAILABLE_MODELS)
    parser.add_argument(
        "--language", default=None,
        help="Language code (e.g. en, pt). Omit to auto-detect.")
    parser.add_argument("--device", default="auto", choices=DEVICES)
    parser.add_argument("--compute", default="auto", choices=COMPUTE_TYPES)
    parser.add_argument(
        "--formats", nargs="+", default=["txt"], choices=list(formats.WRITERS),
        help="One or more output formats.")
    parser.add_argument(
        "--outdir", default=None, help="Output folder (defaults to source folder).")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    audio = Path(args.audio)
    if not audio.is_file():
        print(f"error: file not found: {audio}", file=sys.stderr)
        return 1

    def progress(fraction: float, message: str) -> None:
        bar = "█" * int(fraction * 30)
        print(f"\r[{bar:<30}] {fraction:5.0%}  {message:<28}", end="", flush=True)

    result = Transcriber().transcribe(
        str(audio),
        model=args.model,
        language=args.language,
        device=args.device,
        compute_type=args.compute,
        progress_callback=progress,
    )
    print()  # finish the progress line

    outdir = Path(args.outdir) if args.outdir else audio.parent
    outdir.mkdir(parents=True, exist_ok=True)
    for fmt in args.formats:
        extension, writer = formats.WRITERS[fmt]
        target = outdir / f"{audio.stem}{extension}"
        target.write_text(writer(result), encoding="utf-8")
        print(f"saved {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
