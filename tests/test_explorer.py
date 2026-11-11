"""Explorer batching, safe output names, cancellation and process ownership."""

from __future__ import annotations

import os
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from parrotia.explorer import (
    ExplorerQueue,
    _FileLock,
    _save_transcript,
    _transcribe_files,
    main,
)
from parrotia.transcriber import TranscriptionCancelled


def test_queue_preserves_multiple_paths_and_ignores_partial_requests(tmp_path):
    requests = ExplorerQueue(tmp_path)
    paths = [
        str(tmp_path / "áudio & vídeo (1).MP4"),
        str(tmp_path / "other" / "talk.wav"),
    ]
    requests.publish(paths)
    (tmp_path / "incomplete.tmp").write_text("[", encoding="utf-8")
    assert requests.take() == paths
    assert requests.take() == []
    assert (tmp_path / "incomplete.tmp").exists()


def test_invalid_request_does_not_block_other_requests(tmp_path):
    requests = ExplorerQueue(tmp_path)
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    (tmp_path / "wrong-type.json").write_text('"not a path list"', encoding="utf-8")
    requests.publish(["valid.wav"])
    assert requests.take() == ["valid.wav"]
    assert len(list(tmp_path.glob("*.invalid"))) == 2


def test_concurrent_publication_never_loses_files(tmp_path):
    requests = ExplorerQueue(tmp_path)
    paths = [f"clip {i}.mp4" for i in range(30)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda path: requests.publish([path]), paths))
    assert sorted(requests.take()) == sorted(paths)


def test_existing_transcripts_and_same_stem_sources_are_preserved(tmp_path):
    original = tmp_path / "meeting.txt"
    original.write_text("Keep this", encoding="utf-8")
    first = _save_transcript(tmp_path / "meeting.mp4", "Vídeo")
    second = _save_transcript(tmp_path / "meeting.wav", "Áudio")
    assert original.read_text(encoding="utf-8") == "Keep this"
    assert first.name == "meeting (1).txt"
    assert second.name == "meeting (2).txt"
    assert first.read_text(encoding="utf-8") == "Vídeo"
    assert second.read_text(encoding="utf-8") == "Áudio"


def test_concurrent_output_reservations_are_unique(tmp_path):
    with ThreadPoolExecutor(max_workers=8) as pool:
        outputs = list(
            pool.map(
                lambda i: _save_transcript(tmp_path / "talk.mp3", str(i)), range(20)
            )
        )
    assert len(set(outputs)) == 20
    assert {p.read_text(encoding="utf-8") for p in outputs} == {
        str(i) for i in range(20)
    }


def test_batch_reuses_engine_and_saves_beside_each_source(tmp_path, sample_result):
    first = tmp_path / "one" / "clip.MP4"
    second = tmp_path / "two" / "áudio & more.wav"
    for path in (first, second):
        path.parent.mkdir()
    engine = Mock()
    engine.transcribe.return_value = sample_result
    events = queue.Queue()
    _transcribe_files([str(first), str(second)], engine, threading.Event(), events)
    assert engine.transcribe.call_count == 2
    assert first.with_suffix(".txt").is_file()
    assert second.with_suffix(".txt").is_file()
    assert [engine.transcribe.call_args_list[i].args[0] for i in range(2)] == [
        str(first),
        str(second),
    ]


def test_failed_file_does_not_abort_selection(tmp_path, sample_result):
    engine = Mock()
    engine.transcribe.side_effect = [OSError("Unreadable media"), sample_result]
    events = queue.Queue()
    _transcribe_files(
        [str(tmp_path / "bad.mp4"), str(tmp_path / "good.wav")],
        engine,
        threading.Event(),
        events,
    )
    assert not (tmp_path / "bad.txt").exists()
    assert (tmp_path / "good.txt").exists()
    assert events.get_nowait()[0] == "failed"
    assert events.get_nowait()[0] == "saved"


def test_save_failure_does_not_abort_selection(tmp_path, sample_result):
    engine = Mock()
    engine.transcribe.return_value = sample_result
    events = queue.Queue()
    with patch(
        "parrotia.explorer._save_transcript",
        side_effect=[PermissionError("Read only"), Path("ok.txt")],
    ):
        _transcribe_files(["one.wav", "two.wav"], engine, threading.Event(), events)
    assert events.get_nowait() == ("failed", "one.wav", "Read only")
    assert events.get_nowait() == ("saved", "ok.txt")


def test_unsupported_input_is_rejected_before_loading_model():
    engine = Mock()
    events = queue.Queue()
    _transcribe_files(["notes.txt"], engine, threading.Event(), events)
    engine.transcribe.assert_not_called()
    assert events.get_nowait()[0] == "failed"


@pytest.mark.parametrize("during_transcription", [False, True])
def test_cancel_stops_batch_without_writing(tmp_path, during_transcription):
    engine = Mock()
    engine.transcribe.side_effect = TranscriptionCancelled
    cancel = threading.Event()
    if not during_transcription:
        cancel.set()
    _transcribe_files(
        [str(tmp_path / "one.wav"), str(tmp_path / "two.wav")],
        engine,
        cancel,
        queue.Queue(),
    )
    assert engine.transcribe.call_count == int(during_transcription)
    assert not list(tmp_path.glob("*.txt"))


@pytest.mark.skipif(os.name != "nt", reason="Windows byte-range locking")
def test_owner_lock_excludes_other_instances_and_can_be_reacquired(tmp_path):
    first = _FileLock(tmp_path / "lock")
    second = _FileLock(tmp_path / "lock")
    try:
        assert first.acquire()
        assert not second.acquire()
        first.release()
        assert second.acquire()
    finally:
        first.release()
        second.release()


@pytest.mark.skipif(os.name != "nt", reason="Windows Explorer entry point")
def test_explorer_invocations_join_one_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    first = str(tmp_path / "a & b.mp4")
    second = str(tmp_path / "vídeo.wav")
    received = []

    def window(requests):
        received.extend(requests.take())
        # A second Explorer process should publish and return without a window.
        assert main([second]) == 0
        received.extend(requests.take())

    with patch("parrotia.explorer._run_window", side_effect=window) as run_window:
        assert main([first]) == 0
    run_window.assert_called_once()
    assert received == [first, second]
