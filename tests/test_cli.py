"""Tests for ``parrotia.cli`` — argument parsing and orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from parrotia.cli import _parse_args, main
from parrotia.transcriber import (
    DEFAULT_MODEL,
    Segment,
    TranscriptionResult,
)


# ===================================================================
# Argument parsing
# ===================================================================


class TestParseArgs:
    def test_minimal(self):
        args = _parse_args(["audio.mp3"])
        assert args.audio == "audio.mp3"
        assert args.model == DEFAULT_MODEL
        assert args.language is None
        assert args.device == "auto"
        assert args.compute == "auto"
        assert args.formats == ["txt"]
        assert args.outdir is None
        assert args.benchmark is False

    def test_all_flags(self):
        args = _parse_args(
            [
                "talk.wav",
                "--model",
                "tiny",
                "--language",
                "pt",
                "--device",
                "cpu",
                "--compute",
                "int8",
                "--formats",
                "txt",
                "srt",
                "json",
                "--outdir",
                "/tmp/out",
            ]
        )
        assert args.audio == "talk.wav"
        assert args.model == "tiny"
        assert args.language == "pt"
        assert args.device == "cpu"
        assert args.compute == "int8"
        assert args.formats == ["txt", "srt", "json"]
        assert args.outdir == "/tmp/out"

    def test_benchmark_mode(self):
        args = _parse_args(["audio.mp3", "--benchmark", "--models", "tiny", "base"])
        assert args.benchmark is True
        assert args.models == ["tiny", "base"]

    def test_invalid_model_rejected(self):
        with pytest.raises(SystemExit):
            _parse_args(["audio.mp3", "--model", "nonexistent"])

    def test_invalid_format_rejected(self):
        with pytest.raises(SystemExit):
            _parse_args(["audio.mp3", "--formats", "pdf"])


# ===================================================================
# CLI main — transcription mode
# ===================================================================


class TestMainTranscribe:
    def _fake_result(self, audio_path: str) -> TranscriptionResult:
        return TranscriptionResult(
            source_name=Path(audio_path).name,
            model="tiny",
            language="en",
            duration=10.0,
            segments=[Segment(0.0, 10.0, "Hello world")],
        )

    def test_file_not_found(self, capsys):
        ret = main(["nonexistent.mp3"])
        assert ret == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err

    @patch("parrotia.cli.Transcriber")
    def test_single_format(self, MockTrans, silent_wav, tmp_path):
        instance = MockTrans.return_value
        instance.transcribe.return_value = self._fake_result(str(silent_wav))

        ret = main(
            [
                str(silent_wav),
                "--model",
                "tiny",
                "--formats",
                "txt",
                "--outdir",
                str(tmp_path),
            ]
        )
        assert ret == 0

        out_file = tmp_path / f"{silent_wav.stem}.txt"
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "Hello world" in content

    @patch("parrotia.cli.Transcriber")
    def test_multiple_formats(self, MockTrans, silent_wav, tmp_path):
        instance = MockTrans.return_value
        instance.transcribe.return_value = self._fake_result(str(silent_wav))

        ret = main(
            [
                str(silent_wav),
                "--model",
                "tiny",
                "--formats",
                "txt",
                "srt",
                "json",
                "--outdir",
                str(tmp_path),
            ]
        )
        assert ret == 0

        for ext in (".txt", ".srt", ".json"):
            assert (tmp_path / f"{silent_wav.stem}{ext}").exists()

    @patch("parrotia.cli.Transcriber")
    def test_default_outdir_is_source_folder(self, MockTrans, silent_wav):
        instance = MockTrans.return_value
        instance.transcribe.return_value = self._fake_result(str(silent_wav))

        ret = main([str(silent_wav), "--model", "tiny", "--formats", "txt"])
        assert ret == 0
        assert (silent_wav.parent / f"{silent_wav.stem}.txt").exists()

    @patch("parrotia.cli.Transcriber")
    def test_outdir_created_if_missing(self, MockTrans, silent_wav, tmp_path):
        instance = MockTrans.return_value
        instance.transcribe.return_value = self._fake_result(str(silent_wav))

        new_dir = tmp_path / "subdir" / "deep"
        ret = main(
            [
                str(silent_wav),
                "--model",
                "tiny",
                "--formats",
                "txt",
                "--outdir",
                str(new_dir),
            ]
        )
        assert ret == 0
        assert (new_dir / f"{silent_wav.stem}.txt").exists()


# ===================================================================
# CLI main — benchmark mode
# ===================================================================


class TestMainBenchmark:
    @patch("parrotia.cli.benchmark")
    def test_benchmark_runs(self, mock_bench, silent_wav, tmp_path):
        from parrotia.benchmark import BenchmarkRun

        fake_runs = [
            BenchmarkRun(
                model="tiny",
                duration=10.0,
                load_time=1.0,
                transcribe_time=2.0,
                total_time=3.0,
                segments=5,
            ),
        ]
        mock_bench.benchmark_models.return_value = fake_runs
        mock_bench.format_report.return_value = "Benchmark report\n"
        mock_bench.to_json.return_value = '{"runs": []}\n'

        ret = main(
            [
                str(silent_wav),
                "--benchmark",
                "--models",
                "tiny",
                "--outdir",
                str(tmp_path),
            ]
        )
        assert ret == 0
        assert (tmp_path / f"{silent_wav.stem}.benchmark.txt").exists()
        assert (tmp_path / f"{silent_wav.stem}.benchmark.json").exists()
