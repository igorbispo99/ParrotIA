"""Serialization of transcription results into common subtitle/text formats.

Every writer takes a :class:`~transcriber.TranscriptionResult` and returns a
string, so callers stay free to write to disk, a preview pane, or the clipboard.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable, Dict, Optional

from .transcriber import TranscriptionResult


class OutputBlockedError(PermissionError):
    """Windows refused to let ParrotIA save a transcript into a folder."""


def blocked_write_error(exc: OSError, target: Path) -> Optional[OutputBlockedError]:
    """Describe a protected-folder denial so users can act on it.

    Windows Security's Controlled folder access (ransomware protection) stops
    unrecognized apps from writing into Documents, Desktop, Pictures, Videos
    and Music. Python then reports a misleading "No such file or directory"
    although the folder exists. Returns None for any other error.
    """
    if (
        sys.platform == "win32"
        and isinstance(exc, (FileNotFoundError, PermissionError))
        and target.parent.is_dir()
    ):
        return OutputBlockedError(
            f'Windows blocked saving "{target.name}" in {target.parent}. If '
            "Controlled folder access is on, allow ParrotIA in Windows Security > "
            "Virus & threat protection > Ransomware protection > Allow an app "
            "through Controlled folder access, or save to a folder outside "
            "Documents, Desktop, Pictures, Videos and Music."
        )
    return None


def write_output(target: Path, text: str) -> None:
    """Write a transcript as UTF-8, explaining protected-folder denials."""
    try:
        target.write_text(text, encoding="utf-8")
    except OSError as exc:
        blocked = blocked_write_error(exc, target)
        if blocked is None:
            raise
        raise blocked from exc


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
        + (
            f" (confidence {result.language_probability:.0%})"
            if result.language_probability is not None
            else ""
        ),
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


def _to_subtitles(
    result: TranscriptionResult, *, separator: str, header: str = ""
) -> str:
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
            {"start": s.start, "end": s.end, "text": s.text} for s in result.segments
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
