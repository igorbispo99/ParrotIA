"""Exercise real spawn/IPC, cancellation, shutdown and recovery without models."""

import os
import threading
from pathlib import Path

import pytest

from parrotia import _inference_process as ipc
from parrotia.transcriber import TranscriptionCancelled, TranscriptionResult


def fake_worker(connection, cancelled, backend):
    while True:
        request = connection.recv()
        if request is None:
            connection.close()
            return
        path, settings = request
        mode = settings.get("model")
        if mode == "crash":
            os._exit(7)
        connection.send(("progress", 0.1, "Transcribing…"))
        if mode == "error":
            connection.send(("error", "Invalid audio"))
        elif mode == "hang":
            threading.Event().wait(30)
        elif mode == "cancel":
            cancelled.wait(10)
            connection.send(("cancelled",))
        else:
            connection.send(
                ("result", TranscriptionResult(Path(path).name, "tiny", "en", 1))
            )


@pytest.fixture()
def engine(monkeypatch):
    monkeypatch.setattr(ipc, "_worker_main", fake_worker)
    transcriber = ipc.ProcessTranscriber(backend="whisper.cpp")
    transcriber._SHUTDOWN_TIMEOUT = 0.2
    yield transcriber
    transcriber.close()


def test_progress_and_process_reuse(engine):
    seen = []
    result = engine.transcribe(
        "a.wav", progress_callback=lambda *event: seen.append(event)
    )
    process = engine._process
    assert result.source_name == "a.wav" and seen == [(0.1, "Transcribing…")]
    engine.transcribe("b.wav")
    assert engine._process is process
    engine.close()
    assert not process.is_alive() and process.exitcode == 0
    engine.close()  # Closing twice is safe.


def test_remote_error_does_not_desynchronize_next_request(engine):
    with pytest.raises(RuntimeError, match="Invalid audio"):
        engine.transcribe("a.wav", model="error")
    assert engine.transcribe("b.wav").source_name == "b.wav"


def test_cancellation_reaches_child(engine):
    cancel = threading.Event()
    with pytest.raises(TranscriptionCancelled):
        engine.transcribe(
            "a.wav",
            model="cancel",
            cancel_event=cancel,
            progress_callback=lambda *_: cancel.set(),
        )
    assert engine.transcribe("b.wav").source_name == "b.wav"


def test_crashed_child_is_reported_and_next_request_recovers(engine):
    with pytest.raises(RuntimeError, match="worker stopped unexpectedly"):
        engine.transcribe("a.wav", model="crash")
    assert engine.transcribe("b.wav").source_name == "b.wav"


def test_close_interrupts_unresponsive_native_work(engine):
    ready = threading.Event()
    errors = []

    def transcribe():
        try:
            engine.transcribe(
                "a.wav", model="hang", progress_callback=lambda *_: ready.set()
            )
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=transcribe)
    worker.start()
    assert ready.wait(10)
    process = engine._process
    engine.close()
    worker.join(2)
    assert not worker.is_alive() and not process.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], TranscriptionCancelled)


def test_cancel_interrupts_native_work_that_ignores_abort(engine):
    cancel = threading.Event()
    with pytest.raises(TranscriptionCancelled):
        engine.transcribe(
            "a.wav",
            model="hang",
            cancel_event=cancel,
            progress_callback=lambda *_: cancel.set(),
        )
    assert engine._process is None
    assert engine.transcribe("b.wav").source_name == "b.wav"
