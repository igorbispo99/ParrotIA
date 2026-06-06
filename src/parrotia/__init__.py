"""ParrotIA — fast, free, fully local audio/video transcription via Whisper.

This package bundles a UI-agnostic engine (:mod:`parrotia.transcriber`), output
writers (:mod:`parrotia.formats`), a benchmark harness (:mod:`parrotia.benchmark`),
a headless CLI (:mod:`parrotia.cli`), and a GUI (:mod:`parrotia.app`).

Typical programmatic use::

    from parrotia import Transcriber, WRITERS

    result = Transcriber().transcribe("talk.mp3", model="large-v3-turbo")
    print(WRITERS["txt"][1](result))
"""

from __future__ import annotations

# Single source of truth for the version. Kept as a plain string literal so the
# build backend can read it without importing the package (and its heavy deps).
__version__ = "1.1.0"

# Engine API is import-light (faster-whisper is loaded lazily on first use), so
# it is safe to re-export here. The GUI (parrotia.app) is intentionally *not*
# imported, so ``import parrotia`` never pulls in Tkinter/customtkinter.
from .formats import WRITERS
from .transcriber import (
    AVAILABLE_MODELS,
    COMPUTE_TYPES,
    DEFAULT_MODEL,
    DEVICES,
    LANGUAGES,
    SUPPORTED_EXTENSIONS,
    Segment,
    Transcriber,
    TranscriptionCancelled,
    TranscriptionResult,
)

__all__ = [
    "__version__",
    "AVAILABLE_MODELS",
    "COMPUTE_TYPES",
    "DEFAULT_MODEL",
    "DEVICES",
    "LANGUAGES",
    "SUPPORTED_EXTENSIONS",
    "Segment",
    "Transcriber",
    "TranscriptionCancelled",
    "TranscriptionResult",
    "WRITERS",
]
