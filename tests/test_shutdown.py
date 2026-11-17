"""Window teardown must wait for worker cleanup without blocking Tk."""

import queue
import threading
from types import SimpleNamespace
from unittest.mock import Mock

from parrotia.app import TranscriberApp


def test_close_waits_for_cleanup_before_destroying_window():
    entered, release = threading.Event(), threading.Event()

    def close():
        entered.set()
        assert release.wait(3)

    app = SimpleNamespace(
        _closing=False,
        _cancel_event=threading.Event(),
        _shutdown_complete=threading.Event(),
        _worker=None,
        _transcriber=SimpleNamespace(isolated=True, close=close),
        transcribe_btn=Mock(),
        cancel_btn=Mock(),
        progress=Mock(),
        _set_status=Mock(),
        after=Mock(),
        _finish_close=Mock(),
        destroy=Mock(),
    )
    TranscriberApp._on_close(app)
    assert entered.wait(1)
    assert app._closing and app._cancel_event.is_set()
    app.destroy.assert_not_called()
    app.after.assert_called_with(50, app._finish_close)
    TranscriberApp._on_close(app)  # Repeated close requests do not start more work.
    release.set()
    assert app._shutdown_complete.wait(1)
    app._event_poll = "poll-1"
    app.after_cancel = Mock()
    TranscriberApp._finish_close(app)
    app.after_cancel.assert_called_once_with("poll-1")
    app.destroy.assert_called_once()


def test_closing_suppresses_queued_dialogs_and_progress():
    app = SimpleNamespace(
        _closing=True,
        _event_poll="poll",
        _events=queue.Queue(),
        _handle_event=Mock(),
        after=Mock(),
    )
    app._events.put(("error", RuntimeError("late result")))
    TranscriberApp._drain_events(app)
    app._handle_event.assert_not_called()
    app.after.assert_not_called()


def test_close_during_an_event_does_not_schedule_callbacks_after_destroy():
    app = SimpleNamespace(
        _closing=False, _event_poll="poll", _events=queue.Queue(), after=Mock()
    )
    seen = []

    def handle(event):
        seen.append(event)
        app._closing = True  # e.g. Command-Q inside a completion dialog.

    app._handle_event = handle
    app._events.put(("batch_done",))
    app._events.put(("error", RuntimeError("late error")))
    TranscriberApp._drain_events(app)
    assert seen == [("batch_done",)]
    app.after.assert_not_called()
