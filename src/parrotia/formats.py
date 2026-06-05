"""Serialization of transcription results into common subtitle/text formats.

Every writer takes a :class:`~transcriber.TranscriptionResult` and returns a
string, so callers stay free to write to disk, a preview pane, or the clipboard.
"""

from __future__ import annotations

import json
from typing import Callable, Dict

from .transcriber import TranscriptionResult


def _format_timestamp(seconds: float, *, separator: str) -> str:
    """Format ``seconds`` as ``HH:MM:SS<sep>mmm`` (``,`` for SRT, ``.`` for VTT)."""
    if seconds < 0:
        seconds = 0.0
    milliseconds = round(seconds * 1000.0)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{milliseconds:03d}"


def to_txt(result: TranscriptionResult) -> str:
    """Plain transcript, one segment per line, no timestamps."""
    return "\n".join(segment.text for segment in result.segments).strip() + "\n"


def to_markdown(result: TranscriptionResult) -> str:
    """Readable Markdown document with a metadata header and timestamped lines."""
    lines = [
        f"# Transcript — {result.source_name}",
        "",
        f"- **Model:** {result.model}",
        f"- **Language:** {result.language}"
        + (f" (confidence {result.language_probability:.0%})"
           if result.language_probability is not None else ""),
        f"- **Duration:** {_format_timestamp(result.duration, separator='.')}",
        "",
        "---",
        "",
    ]
    for segment in result.segments:
        start = _format_timestamp(segment.start, separator=".")
        lines.append(f"**[{start}]** {segment.text}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _to_subtitles(result: TranscriptionResult, *, separator: str,
                  header: str = "") -> str:
    blocks = [header] if header else []
    for index, segment in enumerate(result.segments, start=1):
        start = _format_timestamp(segment.start, separator=separator)
        end = _format_timestamp(segment.end, separator=separator)
        blocks.append(f"{index}\n{start} --> {end}\n{segment.text}\n")
    return "\n".join(blocks).strip() + "\n"


def to_srt(result: TranscriptionResult) -> str:
    """SubRip (.srt) subtitles."""
    return _to_subtitles(result, separator=",")


def to_vtt(result: TranscriptionResult) -> str:
    """WebVTT (.vtt) subtitles."""
    return _to_subtitles(result, separator=".", header="WEBVTT\n")


def to_json(result: TranscriptionResult) -> str:
    """Structured JSON with full metadata and per-segment timings."""
    payload = {
        "source": result.source_name,
        "model": result.model,
        "language": result.language,
        "language_probability": result.language_probability,
        "duration": result.duration,
        "segments": [
            {"start": s.start, "end": s.end, "text": s.text}
            for s in result.segments
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


# Registry: format key -> (file extension, writer). Drives both the GUI
# checkboxes and the file-writing loop, so adding a format here is enough.
WRITERS: Dict[str, "tuple[str, Callable[[TranscriptionResult], str]]"] = {
    "txt": (".txt", to_txt),
    "md": (".md", to_markdown),
    "srt": (".srt", to_srt),
    "vtt": (".vtt", to_vtt),
    "json": (".json", to_json),
}
