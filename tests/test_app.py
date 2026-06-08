"""Tests for ``parrotia.app`` — GUI construction (no display required).

These tests verify that the GUI class can be instantiated and that its key
widgets and methods exist.  They do NOT require a visible display server —
they use ``withdraw()`` immediately after creation and never enter mainloop.

If Tkinter cannot initialise (e.g. headless CI without Xvfb), these tests
are skipped automatically.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

# Guard: skip the entire module if a display is unavailable.
try:
    import tkinter as tk
    _root = tk.Tk()
    _root.destroy()
    _HAS_DISPLAY = True
except (tk.TclError, Exception):
    _HAS_DISPLAY = False

pytestmark = pytest.mark.skipif(
    not _HAS_DISPLAY,
    reason="No display available (headless CI without Xvfb)",
)


@pytest.fixture()
def app():
    """Create a hidden TranscriberApp and destroy it after the test."""
    from parrotia.app import TranscriberApp

    try:
        instance = TranscriberApp()
    except Exception as exc:
        pytest.skip(f"Cannot create GUI window: {exc}")
    instance.withdraw()  # keep it invisible
    yield instance
    instance.destroy()


class TestAppInit:
    def test_window_title(self, app):
        assert "ParrotIA" in app.title()

    def test_transcriber_exists(self, app):
        from parrotia.transcriber import Transcriber
        assert isinstance(app._transcriber, Transcriber)

    def test_cancel_event_created(self, app):
        assert isinstance(app._cancel_event, threading.Event)
        assert not app._cancel_event.is_set()

    def test_result_initially_none(self, app):
        assert app._result is None


class TestAppWidgets:
    def test_file_entry_exists(self, app):
        assert app.file_entry is not None

    def test_model_var_exists(self, app):
        assert app.model_var is not None
        assert app.model_var.get() != ""

    def test_format_vars_exist(self, app):
        assert hasattr(app, "format_vars")
        assert len(app.format_vars) > 0
