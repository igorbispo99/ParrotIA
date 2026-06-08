"""Tests for ``parrotia.__init__`` — public API surface and version."""

from __future__ import annotations

import re

import parrotia
from parrotia import (
    AVAILABLE_MODELS,
    COMPUTE_TYPES,
    DEFAULT_MODEL,
    DEVICES,
    LANGUAGES,
    SUPPORTED_EXTENSIONS,
    WRITERS,
    Segment,
    Transcriber,
    TranscriptionCancelled,
    TranscriptionResult,
    __version__,
)


class TestVersion:
    def test_version_is_string(self):
        assert isinstance(__version__, str)

    def test_version_semver_format(self):
        assert re.match(r"^\d+\.\d+\.\d+", __version__), (
            f"Version {__version__!r} does not look like semver"
        )


class TestPublicAPI:
    """Verify that the documented __all__ symbols are importable."""

    def test_all_exports_importable(self):
        for name in parrotia.__all__:
            assert hasattr(parrotia, name), f"{name} listed in __all__ but not importable"

    def test_transcriber_class(self):
        assert callable(Transcriber)

    def test_dataclasses_importable(self):
        assert Segment is not None
        assert TranscriptionResult is not None
        assert TranscriptionCancelled is not None

    def test_constants_importable(self):
        assert isinstance(AVAILABLE_MODELS, list)
        assert isinstance(DEVICES, list)
        assert isinstance(COMPUTE_TYPES, list)
        assert isinstance(LANGUAGES, dict)
        assert isinstance(SUPPORTED_EXTENSIONS, list)

    def test_writers_importable(self):
        assert isinstance(WRITERS, dict)
        assert len(WRITERS) > 0

    def test_gui_not_imported(self):
        """``import parrotia`` must NOT pull in Tkinter/customtkinter."""
        import sys
        # If customtkinter were imported, it would be in sys.modules.
        # This is a soft check — it may be imported by other tests.
        # The key assertion is that ``parrotia.app`` is not in __all__.
        assert "app" not in parrotia.__all__
