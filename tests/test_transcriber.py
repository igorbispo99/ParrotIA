"""Tests for ``parrotia.transcriber`` — model loading, transcription, fallback."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from parrotia.transcriber import (
    AVAILABLE_MODELS,
    COMPUTE_TYPES,
    DEFAULT_MODEL,
    DEVICES,
    LANGUAGES,
    MODEL_SIZES,
    SUPPORTED_EXTENSIONS,
    Segment,
    Transcriber,
    TranscriptionCancelled,
    TranscriptionResult,
    _is_cuda_error,
    _resolve_compute_type,
)


# ===================================================================
# Constants and enumerations
# ===================================================================


class TestConstants:
    def test_available_models_not_empty(self):
        assert len(AVAILABLE_MODELS) > 0

    def test_default_model_in_available(self):
        assert DEFAULT_MODEL in AVAILABLE_MODELS

    def test_devices_contain_expected(self):
        assert "auto" in DEVICES
        assert "cuda" in DEVICES
        assert "cpu" in DEVICES

    def test_compute_types_contain_expected(self):
        for ct in ("auto", "int8", "float16", "float32"):
            assert ct in COMPUTE_TYPES

    def test_supported_extensions_include_common_formats(self):
        for ext in (".mp3", ".wav", ".mp4", ".mkv"):
            assert ext in SUPPORTED_EXTENSIONS

    def test_languages_has_auto_detect(self):
        assert "Auto detect" in LANGUAGES
        assert LANGUAGES["Auto detect"] is None

    def test_languages_codes_unique(self):
        codes = [v for v in LANGUAGES.values() if v is not None]
        assert len(codes) == len(set(codes))

    def test_model_sizes_cover_all_models(self):
        for model in AVAILABLE_MODELS:
            assert model in MODEL_SIZES


# ===================================================================
# Dataclasses
# ===================================================================


class TestSegment:
    def test_creation(self):
        s = Segment(start=1.0, end=2.5, text="hello")
        assert s.start == 1.0
        assert s.end == 2.5
        assert s.text == "hello"

    def test_equality(self):
        a = Segment(0.0, 1.0, "hi")
        b = Segment(0.0, 1.0, "hi")
        assert a == b

    def test_inequality(self):
        a = Segment(0.0, 1.0, "hi")
        b = Segment(0.0, 1.0, "bye")
        assert a != b


class TestTranscriptionResult:
    def test_fields(self, sample_result):
        assert sample_result.source_name == "test_audio.mp3"
        assert sample_result.model == "tiny"
        assert sample_result.language == "en"
        assert sample_result.duration == 30.0
        assert len(sample_result.segments) == 3
        assert sample_result.language_probability == 0.98

    def test_default_segments_empty(self):
        r = TranscriptionResult(
            source_name="a.mp3", model="tiny", language="en", duration=1.0
        )
        assert r.segments == []
        assert r.language_probability is None


# ===================================================================
# Helper functions
# ===================================================================


class TestResolveComputeType:
    def test_explicit_passthrough(self):
        assert _resolve_compute_type("cuda", "float16") == "float16"
        assert _resolve_compute_type("cpu", "int8") == "int8"

    def test_auto_on_cuda(self):
        assert _resolve_compute_type("cuda", "auto") == "float16"

    def test_auto_on_cpu(self):
        assert _resolve_compute_type("cpu", "auto") == "int8"

    def test_auto_on_auto_device(self):
        # "auto" device is not "cuda", so should resolve to int8
        assert _resolve_compute_type("auto", "auto") == "int8"


class TestIsCudaError:
    @pytest.mark.parametrize(
        "msg",
        [
            "Failed to load cublas64_12.dll",
            "Could not load cuDNN shared library",
            "CUDA driver version is insufficient",
            "cannot be loaded because a module was not found",
            "libcudart.so.12: cannot open shared object",
            "GPU out of memory",
        ],
    )
    def test_cuda_errors_detected(self, msg):
        assert _is_cuda_error(RuntimeError(msg))

    @pytest.mark.parametrize(
        "msg",
        [
            "File not found: audio.mp3",
            "Invalid model name",
            "Permission denied",
        ],
    )
    def test_non_cuda_errors_not_detected(self, msg):
        assert not _is_cuda_error(RuntimeError(msg))


# ===================================================================
# Transcriber class
# ===================================================================


class TestTranscriber:
    def test_init_state(self):
        t = Transcriber()
        assert t._model is None
        assert t._model_key is None

    def test_file_not_found(self):
        t = Transcriber()
        with pytest.raises(FileNotFoundError, match="Audio file not found"):
            t.transcribe("/nonexistent/audio.wav")

    @patch("parrotia.transcriber.WhisperModel", create=True)
    def test_transcribe_success(self, MockWhisper, silent_wav, mock_whisper_model):
        """Full transcribe flow with mocked WhisperModel."""
        MockWhisper.return_value = mock_whisper_model
        with patch(
            "parrotia.transcriber.Transcriber._load_model",
            return_value=mock_whisper_model,
        ):
            t = Transcriber()
            result = t.transcribe(str(silent_wav), model="tiny", device="cpu")

        assert isinstance(result, TranscriptionResult)
        assert result.model == "tiny"
        assert result.language == "en"
        assert len(result.segments) == 2

    @patch("parrotia.transcriber.WhisperModel", create=True)
    def test_progress_callback_called(
        self, MockWhisper, silent_wav, mock_whisper_model
    ):
        MockWhisper.return_value = mock_whisper_model
        calls = []

        def cb(fraction, msg):
            calls.append((fraction, msg))

        with patch(
            "parrotia.transcriber.Transcriber._load_model",
            return_value=mock_whisper_model,
        ):
            t = Transcriber()
            t.transcribe(
                str(silent_wav), model="tiny", device="cpu", progress_callback=cb
            )

        assert len(calls) > 0
        # First call should be 0.0 (loading), last should be 1.0 (done)
        assert calls[0][0] == 0.0
        assert calls[-1][0] == 1.0
        assert "Done" in calls[-1][1]

    @patch("parrotia.transcriber.WhisperModel", create=True)
    def test_cancellation(self, MockWhisper, silent_wav, mock_whisper_model):
        MockWhisper.return_value = mock_whisper_model
        cancel = threading.Event()
        cancel.set()  # already cancelled

        with patch(
            "parrotia.transcriber.Transcriber._load_model",
            return_value=mock_whisper_model,
        ):
            t = Transcriber()
            with pytest.raises(TranscriptionCancelled):
                t.transcribe(
                    str(silent_wav), model="tiny", device="cpu", cancel_event=cancel
                )

    @patch("parrotia.transcriber.WhisperModel", create=True)
    def test_gpu_fallback_on_cuda_error(
        self, MockWhisper, silent_wav, mock_whisper_model
    ):
        """When GPU transcription fails with a CUDA error, retry on CPU."""
        call_count = 0

        def fake_load(model, device, compute_type):
            nonlocal call_count
            call_count += 1
            if device != "cpu":
                raise RuntimeError("cublas64_12.dll not found")
            return mock_whisper_model

        with patch.object(Transcriber, "_load_model", side_effect=fake_load):
            t = Transcriber()
            result = t.transcribe(str(silent_wav), model="tiny", device="cuda")

        assert isinstance(result, TranscriptionResult)
        assert call_count == 2  # GPU attempt + CPU fallback

    @patch("parrotia.transcriber.WhisperModel", create=True)
    def test_non_cuda_error_propagates(self, MockWhisper, silent_wav):
        """Non-CUDA errors are not retried and propagate immediately."""

        def fake_load(model, device, compute_type):
            raise ValueError("Something else went wrong")

        with patch.object(Transcriber, "_load_model", side_effect=fake_load):
            t = Transcriber()
            with pytest.raises(ValueError, match="Something else"):
                t.transcribe(str(silent_wav), model="tiny", device="cpu")


class TestModelCache:
    @patch("faster_whisper.WhisperModel")
    def test_same_key_reuses_model(self, MockWhisper):
        mock_model = MagicMock()
        MockWhisper.return_value = mock_model

        t = Transcriber()
        t._load_model("tiny", "cpu", "int8")
        t._load_model("tiny", "cpu", "int8")

        # WhisperModel constructor called only once
        assert MockWhisper.call_count == 1

    @patch("faster_whisper.WhisperModel")
    def test_different_key_reloads(self, MockWhisper):
        MockWhisper.return_value = MagicMock()

        t = Transcriber()
        t._load_model("tiny", "cpu", "int8")
        t._load_model("base", "cpu", "int8")

        assert MockWhisper.call_count == 2

    @patch("faster_whisper.WhisperModel")
    def test_gpu_failure_falls_back_to_cpu(self, MockWhisper):
        """_load_model should fall back to CPU on GPU init failure."""
        call_args = []

        def side_effect(model, device, compute_type):
            call_args.append((model, device, compute_type))
            if device != "cpu":
                raise RuntimeError("CUDA not available")
            return MagicMock()

        MockWhisper.side_effect = side_effect

        t = Transcriber()
        t._load_model("tiny", "cuda", "float16")

        assert len(call_args) == 2
        assert call_args[0] == ("tiny", "cuda", "float16")
        assert call_args[1] == ("tiny", "cpu", "int8")


class TestIsModelCached:
    @patch("parrotia.transcriber.os.path.isdir", return_value=True)
    @patch("parrotia.transcriber.os.listdir", return_value=["abc123"])
    def test_cached_model_returns_true(self, mock_listdir, mock_isdir):
        assert Transcriber.is_model_cached("tiny") is True

    @patch("parrotia.transcriber.os.path.isdir", return_value=False)
    def test_not_cached_returns_false(self, mock_isdir):
        assert Transcriber.is_model_cached("tiny") is False

    def test_unknown_model_returns_true(self):
        """Custom/unknown model names should assume available."""
        assert Transcriber.is_model_cached("my-custom-model") is True


class TestTranscriptionCancelled:
    def test_is_exception(self):
        assert issubclass(TranscriptionCancelled, Exception)

    def test_can_raise_and_catch(self):
        with pytest.raises(TranscriptionCancelled):
            raise TranscriptionCancelled()
