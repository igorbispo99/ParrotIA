"""Shared fixtures for the ParrotIA test suite.

Every fixture that creates temporary files or directories uses ``tmp_path``
(pytest built-in) so artefacts are cleaned up automatically.
"""

from __future__ import annotations

import struct
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import List
from unittest.mock import MagicMock

import pytest

from parrotia.transcriber import Segment, TranscriptionResult


# ---------------------------------------------------------------------------
# Reusable domain objects
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_segments() -> List[Segment]:
    """Three realistic segments spanning a ~30 s audio clip."""
    return [
        Segment(start=0.0, end=10.5, text="Hello, this is a test."),
        Segment(start=10.5, end=20.0, text="Testing ParrotIA transcription."),
        Segment(start=20.0, end=30.0, text="Final segment of the audio."),
    ]


@pytest.fixture()
def sample_result(sample_segments: List[Segment]) -> TranscriptionResult:
    """A fully populated ``TranscriptionResult``."""
    return TranscriptionResult(
        source_name="test_audio.mp3",
        model="tiny",
        language="en",
        duration=30.0,
        segments=sample_segments,
        language_probability=0.98,
    )


@pytest.fixture()
def result_no_probability(sample_segments: List[Segment]) -> TranscriptionResult:
    """Result where ``language_probability`` is ``None`` (auto-detect off)."""
    return TranscriptionResult(
        source_name="test_audio.mp3",
        model="tiny",
        language="en",
        duration=30.0,
        segments=sample_segments,
        language_probability=None,
    )


@pytest.fixture()
def empty_result() -> TranscriptionResult:
    """A result with no segments (e.g. silence)."""
    return TranscriptionResult(
        source_name="silence.wav",
        model="base",
        language="en",
        duration=5.0,
        segments=[],
        language_probability=0.99,
    )


# ---------------------------------------------------------------------------
# Temporary audio file (valid WAV — 0.5 s of silence)
# ---------------------------------------------------------------------------

def _write_silent_wav(path: Path, duration: float = 0.5, rate: int = 16000) -> Path:
    """Create a minimal valid WAV file filled with silence."""
    n_frames = int(rate * duration)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(struct.pack(f"<{n_frames}h", *([0] * n_frames)))
    return path


@pytest.fixture()
def silent_wav(tmp_path: Path) -> Path:
    """A tiny, valid .wav file (0.5 s silence) in a temp directory."""
    return _write_silent_wav(tmp_path / "silence.wav")


@pytest.fixture()
def silent_wav_factory(tmp_path: Path):
    """Factory fixture: call with a filename to create a silent WAV."""
    def factory(name: str = "audio.wav", duration: float = 0.5) -> Path:
        return _write_silent_wav(tmp_path / name, duration=duration)
    return factory


# ---------------------------------------------------------------------------
# Mock Whisper model
# ---------------------------------------------------------------------------

@dataclass
class _FakeInfo:
    duration: float = 10.0
    language: str = "en"
    language_probability: float = 0.95


@dataclass
class _FakeSegment:
    start: float = 0.0
    end: float = 5.0
    text: str = "Hello world"


@pytest.fixture()
def mock_whisper_model():
    """A ``MagicMock`` mimicking ``faster_whisper.WhisperModel``."""
    model = MagicMock()
    model.transcribe.return_value = (
        [_FakeSegment(0.0, 5.0, "Hello world"),
         _FakeSegment(5.0, 10.0, "Second segment")],
        _FakeInfo(),
    )
    return model
