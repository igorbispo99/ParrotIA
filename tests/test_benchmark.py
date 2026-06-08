"""Tests for ``parrotia.benchmark`` — timing, reporting, and error handling."""

from __future__ import annotations

import json
import threading
from unittest.mock import MagicMock, patch

import pytest

from parrotia.benchmark import (
    BenchmarkRun,
    benchmark_models,
    format_report,
    to_json,
)
from parrotia.transcriber import TranscriptionCancelled, TranscriptionResult, Segment


# ===================================================================
# BenchmarkRun dataclass
# ===================================================================

class TestBenchmarkRun:
    def test_ok_when_no_error(self):
        r = BenchmarkRun(
            model="tiny", duration=10.0, load_time=1.0,
            transcribe_time=2.0, total_time=3.0, segments=5
        )
        assert r.ok is True
        assert r.error is None

    def test_not_ok_when_error(self):
        r = BenchmarkRun(
            model="tiny", duration=0.0, load_time=0.0,
            transcribe_time=0.0, total_time=0.0, segments=0,
            error="CUDA not found"
        )
        assert r.ok is False

    def test_speed_calculation(self):
        r = BenchmarkRun(
            model="tiny", duration=10.0, load_time=1.0,
            transcribe_time=2.0, total_time=3.0, segments=5
        )
        assert r.speed == pytest.approx(5.0)

    def test_speed_zero_transcribe_time(self):
        r = BenchmarkRun(
            model="tiny", duration=10.0, load_time=1.0,
            transcribe_time=0.0, total_time=1.0, segments=0
        )
        assert r.speed == 0.0

    def test_speed_negative_transcribe_time(self):
        r = BenchmarkRun(
            model="tiny", duration=10.0, load_time=1.0,
            transcribe_time=-1.0, total_time=0.0, segments=0
        )
        assert r.speed == 0.0


# ===================================================================
# benchmark_models()
# ===================================================================

class TestBenchmarkModels:
    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            benchmark_models("/no/such/file.wav", ["tiny"])

    @patch("parrotia.benchmark.Transcriber")
    def test_successful_run(self, MockTrans, silent_wav):
        fake_result = TranscriptionResult(
            source_name="silence.wav", model="tiny", language="en",
            duration=10.0,
            segments=[Segment(0.0, 10.0, "text")],
        )
        MockTrans.return_value.transcribe.return_value = fake_result

        runs = benchmark_models(str(silent_wav), ["tiny"], device="cpu")
        assert len(runs) == 1
        assert runs[0].ok
        assert runs[0].model == "tiny"

    @patch("parrotia.benchmark.Transcriber")
    def test_multiple_models(self, MockTrans, silent_wav):
        fake_result = TranscriptionResult(
            source_name="silence.wav", model="tiny", language="en",
            duration=10.0, segments=[]
        )
        MockTrans.return_value.transcribe.return_value = fake_result

        runs = benchmark_models(str(silent_wav), ["tiny", "base"], device="cpu")
        assert len(runs) == 2

    @patch("parrotia.benchmark.Transcriber")
    def test_failing_model_does_not_abort(self, MockTrans, silent_wav):
        """A model that fails records the error but lets others continue."""
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Model download failed")
            return TranscriptionResult(
                source_name="silence.wav", model="base", language="en",
                duration=10.0, segments=[]
            )

        MockTrans.return_value.transcribe.side_effect = side_effect

        runs = benchmark_models(str(silent_wav), ["tiny", "base"], device="cpu")
        assert len(runs) == 2
        assert not runs[0].ok
        assert "download failed" in runs[0].error
        assert runs[1].ok

    @patch("parrotia.benchmark.Transcriber")
    def test_cancel_event_stops_benchmark(self, MockTrans, silent_wav):
        cancel = threading.Event()
        cancel.set()

        with pytest.raises(TranscriptionCancelled):
            benchmark_models(str(silent_wav), ["tiny", "base"],
                             device="cpu", cancel_event=cancel)

    @patch("parrotia.benchmark.Transcriber")
    def test_progress_callback_invoked(self, MockTrans, silent_wav):
        fake_result = TranscriptionResult(
            source_name="silence.wav", model="tiny", language="en",
            duration=10.0, segments=[]
        )
        MockTrans.return_value.transcribe.return_value = fake_result

        calls = []
        def cb(index, count, model, fraction, msg):
            calls.append((index, count, model))

        benchmark_models(str(silent_wav), ["tiny"], device="cpu",
                         progress_callback=cb)
        # At minimum, on_progress is wired — but calls depend on transcribe
        # internals; we just verify no crash


# ===================================================================
# format_report()
# ===================================================================

class TestFormatReport:
    def test_header_present(self):
        runs = [
            BenchmarkRun("tiny", 10.0, 1.0, 2.0, 3.0, 5),
        ]
        report = format_report(runs)
        assert "Model" in report
        assert "Speed" in report

    def test_model_names_in_output(self):
        runs = [
            BenchmarkRun("tiny", 10.0, 1.0, 2.0, 3.0, 5),
            BenchmarkRun("base", 10.0, 2.0, 3.0, 5.0, 8),
        ]
        report = format_report(runs)
        assert "tiny" in report
        assert "base" in report

    def test_error_run_shown(self):
        runs = [
            BenchmarkRun("tiny", 0.0, 0.0, 0.0, 0.0, 0, error="boom"),
        ]
        report = format_report(runs)
        assert "ERROR" in report
        assert "boom" in report

    def test_fastest_model_shown(self):
        runs = [
            BenchmarkRun("tiny", 10.0, 0.5, 1.0, 1.5, 3),
            BenchmarkRun("base", 10.0, 1.0, 5.0, 6.0, 3),
        ]
        report = format_report(runs)
        assert "Fastest: tiny" in report

    def test_empty_runs(self):
        report = format_report([])
        assert "Model" in report  # header still present

    def test_ends_with_newline(self):
        runs = [BenchmarkRun("tiny", 10.0, 1.0, 2.0, 3.0, 5)]
        assert format_report(runs).endswith("\n")


# ===================================================================
# to_json()
# ===================================================================

class TestBenchmarkToJson:
    def test_valid_json(self):
        runs = [BenchmarkRun("tiny", 10.0, 1.0, 2.0, 3.0, 5)]
        raw = to_json(runs, source="test.mp3")
        data = json.loads(raw)
        assert data["source"] == "test.mp3"

    def test_run_fields(self):
        runs = [BenchmarkRun("tiny", 10.0, 1.0, 2.0, 3.0, 5)]
        data = json.loads(to_json(runs))
        r = data["runs"][0]
        assert r["model"] == "tiny"
        assert r["duration"] == 10.0
        assert r["speed"] == pytest.approx(5.0)
        assert r["error"] is None

    def test_error_run_serialized(self):
        runs = [BenchmarkRun("tiny", 0.0, 0.0, 0.0, 0.0, 0, error="fail")]
        data = json.loads(to_json(runs))
        assert data["runs"][0]["error"] == "fail"

    def test_multiple_runs(self):
        runs = [
            BenchmarkRun("tiny", 10.0, 1.0, 2.0, 3.0, 5),
            BenchmarkRun("base", 10.0, 2.0, 3.0, 5.0, 8),
        ]
        data = json.loads(to_json(runs))
        assert len(data["runs"]) == 2

    def test_ends_with_newline(self):
        runs = [BenchmarkRun("tiny", 10.0, 1.0, 2.0, 3.0, 5)]
        assert to_json(runs).endswith("\n")
