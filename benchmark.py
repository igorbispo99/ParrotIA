"""Benchmark transcription speed across Whisper models.

Runs the same audio file through several models and times each one, separating
the one-off model *load* cost from the actual *decoding* cost. The headline
metric is the real-time factor (``speed``): how many seconds of audio are
transcribed per second of wall-clock time — higher is faster.

Like :mod:`transcriber`, this module is UI-agnostic: it returns plain dataclass
results and streams progress through a callback, so the GUI, the CLI, and tests
can all drive it.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from transcriber import TranscriptionCancelled, Transcriber


@dataclass
class BenchmarkRun:
    """Timing for a single model over one audio file."""

    model: str
    duration: float            # audio length, seconds
    load_time: float           # model load (download/init), seconds
    transcribe_time: float     # decoding only, seconds
    total_time: float          # load + transcribe, seconds
    segments: int
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def speed(self) -> float:
        """Real-time factor: audio seconds decoded per wall-clock second."""
        if self.transcribe_time <= 0:
            return 0.0
        return self.duration / self.transcribe_time


# (model_index, model_count, model, fraction_in_model, status_message)
BenchmarkProgressCallback = Callable[[int, int, str, float, str], None]


def benchmark_models(
    audio_path: str,
    models: List[str],
    *,
    language: Optional[str] = None,
    device: str = "auto",
    compute_type: str = "auto",
    progress_callback: Optional[BenchmarkProgressCallback] = None,
    cancel_event: Optional[threading.Event] = None,
) -> List[BenchmarkRun]:
    """Transcribe ``audio_path`` with each model in ``models`` and time it.

    A failing model (e.g. an unavailable download) records its error and the
    run continues with the next one, so a single bad model never aborts the
    whole comparison. Setting ``cancel_event`` stops cleanly between models and
    raises :class:`~transcriber.TranscriptionCancelled`.
    """
    path = Path(audio_path)
    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    runs: List[BenchmarkRun] = []
    total = len(models)
    for index, model in enumerate(models):
        if cancel_event is not None and cancel_event.is_set():
            raise TranscriptionCancelled()

        # A fresh engine per model guarantees the model is loaded from scratch,
        # so a model cached by a previous run never reports a misleading ~0s
        # load time and skews the comparison.
        engine = Transcriber()
        start = time.perf_counter()
        # ``transcribe`` reports fraction >= 0.05 only after the model is
        # loaded; we capture that instant to split load time from decode time.
        loaded_at: List[float] = []

        def on_progress(fraction: float, message: str, _model=model,
                        _index=index) -> None:
            if not loaded_at and fraction >= 0.05:
                loaded_at.append(time.perf_counter())
            if progress_callback is not None:
                progress_callback(_index, total, _model, fraction, message)

        try:
            result = engine.transcribe(
                str(path),
                model=model,
                language=language,
                device=device,
                compute_type=compute_type,
                progress_callback=on_progress,
                cancel_event=cancel_event,
            )
            end = time.perf_counter()
            loaded = loaded_at[0] if loaded_at else start
            runs.append(BenchmarkRun(
                model=model,
                duration=result.duration,
                load_time=loaded - start,
                transcribe_time=end - loaded,
                total_time=end - start,
                segments=len(result.segments),
            ))
        except TranscriptionCancelled:
            raise
        except Exception as exc:  # noqa: BLE001 — record and move on
            runs.append(BenchmarkRun(
                model=model, duration=0.0, load_time=0.0,
                transcribe_time=0.0, total_time=0.0, segments=0,
                error=str(exc),
            ))
    return runs


def format_report(runs: List[BenchmarkRun]) -> str:
    """Render benchmark runs as a fixed-width comparison table."""
    header = (
        f"{'Model':<18}{'Audio':>9}{'Load':>9}"
        f"{'Decode':>9}{'Speed':>10}{'Segments':>10}"
    )
    lines = [header, "-" * len(header)]
    for run in runs:
        if not run.ok:
            lines.append(f"{run.model:<18}ERROR: {run.error}")
            continue
        lines.append(
            f"{run.model:<18}"
            f"{run.duration:>8.1f}s"
            f"{run.load_time:>8.1f}s"
            f"{run.transcribe_time:>8.1f}s"
            f"{run.speed:>9.1f}x"
            f"{run.segments:>10}"
        )

    ranked = sorted(
        (r for r in runs if r.ok and r.transcribe_time > 0),
        key=lambda r: r.speed, reverse=True,
    )
    if ranked:
        fastest = ranked[0]
        lines.append("")
        lines.append(
            f"Fastest: {fastest.model} — {fastest.speed:.1f}x real-time "
            f"({fastest.transcribe_time:.1f}s to decode "
            f"{fastest.duration:.1f}s of audio)"
        )
    return "\n".join(lines) + "\n"


def to_json(runs: List[BenchmarkRun], *, source: str = "") -> str:
    """Structured JSON report — handy for plotting or regression tracking."""
    import json

    payload = {
        "source": source,
        "runs": [
            {
                "model": r.model,
                "duration": r.duration,
                "load_time": r.load_time,
                "transcribe_time": r.transcribe_time,
                "total_time": r.total_time,
                "speed": r.speed,
                "segments": r.segments,
                "error": r.error,
            }
            for r in runs
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
