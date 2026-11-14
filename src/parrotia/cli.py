"""Headless transcription — useful for batch jobs, scripting, and testing.

Example:
    parrotia "talk.mp3" --model large-v3-turbo --formats txt srt --language en

Benchmark several models against one file and print a speed comparison:
    parrotia "talk.mp3" --benchmark --models tiny base small large-v3-turbo
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

from . import benchmark, formats
from .transcriber import (
    BACKENDS,
    DEFAULT_MODEL,
    Transcriber,
    backend_options,
)


def _all_choices(attribute: str) -> "list[str]":
    """Union of one option list across every backend, in first-seen order."""
    seen: "dict[str, None]" = {}
    for name in BACKENDS:
        for value in getattr(backend_options(name), attribute):
            seen.setdefault(value, None)
    return list(seen)


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local Whisper transcription.")
    parser.add_argument("audio", help="Path to the audio/video file.")
    parser.add_argument(
        "--backend",
        default=None,
        choices=BACKENDS,
        help="Inference engine (default: faster-whisper if installed, else whisper.cpp).",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, choices=_all_choices("models"))
    parser.add_argument(
        "--language",
        default=None,
        help="Language code (e.g. en, pt). Omit to auto-detect.",
    )
    parser.add_argument("--device", default="auto", choices=_all_choices("devices"))
    parser.add_argument(
        "--compute", default="auto", choices=_all_choices("compute_types")
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        default=["txt"],
        choices=list(formats.WRITERS),
        help="One or more output formats.",
    )
    parser.add_argument(
        "--outdir", default=None, help="Output folder (defaults to source folder)."
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Time several models on the file and print a speed comparison "
        "instead of transcribing.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=None,
        choices=_all_choices("models"),
        help="Models to compare in --benchmark mode (default: all).",
    )
    args = parser.parse_args(argv)

    # Each backend supports a subset of the combined choices above.
    try:
        options = backend_options(args.backend)
    except ValueError as exc:  # e.g. an invalid PARROTIA_BACKEND
        parser.error(str(exc))
    args.backend = options.name
    for flag, values, allowed in (
        ("--model", [args.model], options.models),
        ("--models", args.models or [], options.models),
        ("--device", [args.device], options.devices),
        ("--compute", [args.compute], options.compute_types),
    ):
        unsupported = [v for v in values if v not in allowed]
        if unsupported:
            parser.error(
                f"{flag} {' '.join(unsupported)} is not supported by the "
                f"{options.name} backend (choose from: {', '.join(allowed)})"
            )
    return args


def _run_benchmark(args, audio: Path) -> int:
    models = args.models or backend_options(args.backend).models
    total = len(models)

    def progress(index, count, model, fraction, message) -> None:
        bar = "█" * int(fraction * 24)
        print(
            f"\r[{index + 1}/{count}] {model:<16} "
            f"[{bar:<24}] {fraction:4.0%} {message:<24}",
            end="",
            flush=True,
        )

    print(f"Benchmarking {total} model(s) on {audio.name}…")
    runs = benchmark.benchmark_models(
        str(audio),
        list(models),
        language=args.language,
        device=args.device,
        compute_type=args.compute,
        progress_callback=progress,
        backend=args.backend,
    )
    print("\n")
    report = benchmark.format_report(runs)
    print(report)

    outdir = Path(args.outdir) if args.outdir else audio.parent
    outdir.mkdir(parents=True, exist_ok=True)
    txt_path = outdir / f"{audio.stem}.benchmark.txt"
    json_path = outdir / f"{audio.stem}.benchmark.json"
    txt_path.write_text(report, encoding="utf-8")
    json_path.write_text(benchmark.to_json(runs, source=audio.name), encoding="utf-8")
    print(f"saved {txt_path}")
    print(f"saved {json_path}")
    return 0


def main(argv=None) -> int:
    args = _parse_args(argv)
    audio = Path(args.audio)
    if not audio.is_file():
        print(f"error: file not found: {audio}", file=sys.stderr)
        return 1

    if args.benchmark:
        return _run_benchmark(args, audio)

    def progress(fraction: float, message: str) -> None:
        bar = "█" * int(fraction * 30)
        print(f"\r[{bar:<30}] {fraction:5.0%}  {message:<28}", end="", flush=True)

    result = Transcriber(backend=args.backend).transcribe(
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
