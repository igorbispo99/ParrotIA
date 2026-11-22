"""Desktop preferences use the host portal and never call Tk from a worker."""

import queue
import subprocess
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from parrotia._desktop import AppearanceWatcher, linux_appearance


@pytest.mark.parametrize("value,mode", [(1, "Dark"), (2, "Light")])
def test_portal_preference_wins_over_legacy_settings(value, mode):
    with patch("parrotia._desktop._read", return_value=f"(<uint32 {value}>,)") as read:
        assert linux_appearance() == mode
    assert len(read.call_args_list) == 1
    assert "org.freedesktop.portal.Settings.ReadOne" in read.call_args.args[0]


def test_older_portal_read_with_nested_variant():
    with patch("parrotia._desktop._read", side_effect=[None, "(<<uint32 1>>,)"]):
        assert linux_appearance() == "Dark"


@pytest.mark.parametrize(
    "values,mode",
    [
        (["(<uint32 0>,)", "'prefer-dark'"], "Dark"),
        (["(<uint32 0>,)", "'prefer-light'"], "Light"),
        ([None, None, "'default'", "'Adwaita-dark'"], "Dark"),
        ([None, None, None, "'Yaru'"], "Light"),
        ([None, None, None, None], None),
    ],
)
def test_unavailable_or_default_portal_uses_legacy_gnome(values, mode):
    with patch("parrotia._desktop._read", side_effect=values):
        assert linux_appearance() == mode


@pytest.mark.parametrize(
    "failure", [FileNotFoundError(), subprocess.TimeoutExpired("gdbus", 1)]
)
def test_missing_or_unresponsive_tools_are_bounded(failure):
    with patch("parrotia._desktop.subprocess.run", side_effect=failure) as run:
        assert linux_appearance() is None
    assert all(call.kwargs["timeout"] == 1.5 for call in run.call_args_list)


def test_snap_uses_its_bundled_portal_client(monkeypatch):
    monkeypatch.setenv("SNAP", "/snap/parrotia/123")
    result = subprocess.CompletedProcess([], 0, "(<uint32 1>,)", "")
    with patch("parrotia._desktop.subprocess.run", return_value=result) as run:
        assert linux_appearance() == "Dark"
    assert Path(run.call_args.args[0][0]) == Path("/snap/parrotia/123/usr/bin/gdbus")


def test_watcher_publishes_changes_off_ui_thread_and_stops():
    events = queue.Queue()
    modes = iter(["Dark", None, "Dark", "Light"])
    main_thread = threading.get_ident()

    def reader():
        assert threading.get_ident() != main_thread
        return next(modes, "Light")

    watcher = AppearanceWatcher(events.put, "Light", reader=reader, interval=0.01)
    try:
        assert events.get(timeout=1) == "Dark"
        assert events.get(timeout=1) == "Light"
    finally:
        watcher.stop()
        watcher._thread.join(timeout=1)
    assert not watcher._thread.is_alive()
    assert events.empty()
