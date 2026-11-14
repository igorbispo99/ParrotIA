"""Tests for the whisper.cpp backend and backend selection.

pywhispercpp is never imported: model loading, decoding and ffmpeg are mocked,
so these run on any platform without native libraries or downloads.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import subprocess
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from parrotia import _whispercpp as wcpp
from parrotia.cli import _parse_args
from parrotia.transcriber import (
    BACKENDS,
    DEFAULT_MODEL,
    FASTER_WHISPER,
    WHISPER_CPP,
    Transcriber,
    TranscriptionCancelled,
    backend_options,
    detect_backend,
)

np = pytest.importorskip("numpy")


@pytest.fixture()
def models_dir(tmp_path, monkeypatch) -> Path:
    directory = tmp_path / "models"
    monkeypatch.setenv("PARROTIA_MODELS_DIR", str(directory))
    return directory


def _spec_for(payload: bytes, name: str = "ggml-test.bin") -> wcpp.ModelFile:
    return wcpp.ModelFile(
        repo="example/repo",
        revision="0" * 40,
        filename=name,
        size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )


class _FakeResponse(io.BytesIO):
    """Minimal stand-in for the object ``urllib.request.urlopen`` returns."""

    def __init__(self, payload: bytes, status: int = 200) -> None:
        super().__init__(payload)
        self.status = status


# ===================================================================
# Backend selection
# ===================================================================


class TestDetectBackend:
    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("PARROTIA_BACKEND", "whisper.cpp")
        assert detect_backend() == WHISPER_CPP

    def test_env_override_is_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("PARROTIA_BACKEND", " Whisper.CPP ")
        assert detect_backend() == WHISPER_CPP

    def test_invalid_env_raises(self, monkeypatch):
        monkeypatch.setenv("PARROTIA_BACKEND", "openvino")
        with pytest.raises(ValueError, match="PARROTIA_BACKEND"):
            detect_backend()

    @pytest.mark.parametrize(
        "installed, expected",
        [
            ({"faster_whisper", "pywhispercpp"}, FASTER_WHISPER),
            ({"pywhispercpp"}, WHISPER_CPP),
            (set(), FASTER_WHISPER),
        ],
    )
    def test_auto_detection(self, monkeypatch, installed, expected):
        monkeypatch.delenv("PARROTIA_BACKEND", raising=False)
        with patch(
            "parrotia.transcriber._module_available", side_effect=installed.__contains__
        ):
            assert detect_backend() == expected

    def test_transcriber_rejects_unknown_backend(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            Transcriber(backend="nope")

    def test_transcriber_records_backend(self):
        assert Transcriber(backend=WHISPER_CPP).backend == WHISPER_CPP


class TestBackendOptions:
    @pytest.mark.parametrize("backend", BACKENDS)
    def test_default_model_offered(self, backend):
        options = backend_options(backend)
        assert options.default_model == DEFAULT_MODEL
        assert DEFAULT_MODEL in options.models

    @pytest.mark.parametrize("backend", BACKENDS)
    def test_sizes_cover_models(self, backend):
        options = backend_options(backend)
        assert set(options.models) <= set(options.model_sizes)

    def test_whispercpp_is_cpu_only(self):
        options = backend_options(WHISPER_CPP)
        assert "cuda" not in options.devices
        assert options.compute_types == ["auto"]

    def test_unknown_backend(self):
        with pytest.raises(ValueError):
            backend_options("nope")


# ===================================================================
# Model table and storage
# ===================================================================


class TestModelFiles:
    @pytest.mark.parametrize("name", list(wcpp.MODEL_FILES) + ["vad"])
    def test_pinned_and_checksummed(self, name):
        spec = wcpp.VAD_MODEL if name == "vad" else wcpp.MODEL_FILES[name]
        assert re.fullmatch(r"[0-9a-f]{40}", spec.revision)
        assert re.fullmatch(r"[0-9a-f]{64}", spec.sha256)
        assert spec.size > 0
        assert spec.url == (
            f"https://huggingface.co/{spec.repo}/resolve/{spec.revision}/{spec.filename}"
        )

    def test_human_size(self):
        assert wcpp.human_size(1_624_555_275) == "~1.6 GB"
        assert wcpp.human_size(77_691_713) == "~78 MB"

    def test_models_dir_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PARROTIA_MODELS_DIR", str(tmp_path))
        assert wcpp.models_dir() == tmp_path

    @pytest.mark.skipif(os.name == "nt", reason="XDG layout applies to POSIX")
    def test_models_dir_xdg(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PARROTIA_MODELS_DIR", raising=False)
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        assert wcpp.models_dir() == tmp_path / "parrotia" / "models"

    def test_partial_file_is_not_downloaded(self, models_dir):
        spec = _spec_for(b"0123456789")
        models_dir.mkdir()
        (models_dir / spec.filename).write_bytes(b"01234")
        assert wcpp.is_downloaded(spec) is False
        (models_dir / spec.filename).write_bytes(b"0123456789")
        assert wcpp.is_downloaded(spec) is True

    def test_is_model_cached_uses_backend(self, models_dir, monkeypatch):
        spec = _spec_for(b"abc")
        monkeypatch.setitem(wcpp.MODEL_FILES, "tiny", spec)
        assert Transcriber.is_model_cached("tiny", WHISPER_CPP) is False
        models_dir.mkdir()
        (models_dir / spec.filename).write_bytes(b"abc")
        assert Transcriber.is_model_cached("tiny", WHISPER_CPP) is True


# ===================================================================
# Downloads
# ===================================================================


class TestEnsureDownloaded:
    PAYLOAD = b"ggml model bytes " * 1000

    def test_fresh_download_verified_and_renamed(self, models_dir):
        spec = _spec_for(self.PAYLOAD)
        progress = []
        with patch.object(
            wcpp.urllib.request, "urlopen", return_value=_FakeResponse(self.PAYLOAD)
        ) as urlopen:
            path = wcpp.ensure_downloaded(spec, lambda d, t: progress.append((d, t)))

        assert path == models_dir / spec.filename
        assert path.read_bytes() == self.PAYLOAD
        assert not path.with_name(path.name + ".part").exists()
        assert progress[-1] == (len(self.PAYLOAD), len(self.PAYLOAD))
        assert urlopen.call_args.args[0].full_url == spec.url

    def test_already_downloaded_skips_network(self, models_dir):
        spec = _spec_for(self.PAYLOAD)
        models_dir.mkdir()
        (models_dir / spec.filename).write_bytes(self.PAYLOAD)
        with patch.object(wcpp.urllib.request, "urlopen") as urlopen:
            wcpp.ensure_downloaded(spec)
        urlopen.assert_not_called()

    def test_checksum_mismatch_rejected(self, models_dir):
        spec = _spec_for(self.PAYLOAD)
        corrupt = b"X" + self.PAYLOAD[1:]
        with patch.object(
            wcpp.urllib.request, "urlopen", return_value=_FakeResponse(corrupt)
        ):
            with pytest.raises(RuntimeError, match="failed verification"):
                wcpp.ensure_downloaded(spec)
        assert not (models_dir / spec.filename).exists()
        assert not (models_dir / (spec.filename + ".part")).exists()

    def test_resumes_partial_download(self, models_dir):
        spec = _spec_for(self.PAYLOAD)
        models_dir.mkdir()
        half = len(self.PAYLOAD) // 2
        (models_dir / (spec.filename + ".part")).write_bytes(self.PAYLOAD[:half])
        with patch.object(
            wcpp.urllib.request,
            "urlopen",
            return_value=_FakeResponse(self.PAYLOAD[half:], status=206),
        ) as urlopen:
            path = wcpp.ensure_downloaded(spec)

        assert urlopen.call_args.args[0].get_header("Range") == f"bytes={half}-"
        assert path.read_bytes() == self.PAYLOAD

    def test_restarts_when_range_ignored(self, models_dir):
        spec = _spec_for(self.PAYLOAD)
        models_dir.mkdir()
        (models_dir / (spec.filename + ".part")).write_bytes(b"stale")
        with patch.object(
            wcpp.urllib.request,
            "urlopen",
            return_value=_FakeResponse(self.PAYLOAD, status=200),
        ):
            path = wcpp.ensure_downloaded(spec)
        assert path.read_bytes() == self.PAYLOAD

    def test_cancel_keeps_partial_for_resume(self, models_dir):
        spec = _spec_for(self.PAYLOAD)

        def cancel():
            raise TranscriptionCancelled()

        with patch.object(
            wcpp.urllib.request, "urlopen", return_value=_FakeResponse(self.PAYLOAD)
        ):
            with pytest.raises(TranscriptionCancelled):
                wcpp.ensure_downloaded(spec, check_cancel=cancel)
        assert not (models_dir / spec.filename).exists()
        assert (models_dir / (spec.filename + ".part")).exists()


# ===================================================================
# Audio decoding
# ===================================================================


class TestLoadAudio:
    def test_missing_ffmpeg(self):
        with patch.object(wcpp.shutil, "which", return_value=None):
            with pytest.raises(RuntimeError, match="ffmpeg is required"):
                wcpp.load_audio("talk.mp3")

    def test_decode_failure_reports_ffmpeg_error(self):
        failed = subprocess.CompletedProcess(
            [], 1, stdout=b"", stderr=b"noise\ntalk.wma: Invalid data found\n"
        )
        with patch.object(wcpp.shutil, "which", return_value="/usr/bin/ffmpeg"), \
                patch.object(wcpp.subprocess, "run", return_value=failed):
            with pytest.raises(RuntimeError, match="talk.wma: Invalid data found"):
                wcpp.load_audio("talk.wma")

    def test_decodes_float32_pcm(self):
        samples = np.array([0.0, 0.5, -0.25], dtype=np.float32)
        ok = subprocess.CompletedProcess([], 0, stdout=samples.tobytes(), stderr=b"")
        with patch.object(wcpp.shutil, "which", return_value="/usr/bin/ffmpeg"), \
                patch.object(wcpp.subprocess, "run", return_value=ok) as run:
            audio = wcpp.load_audio("talk.mp3")

        np.testing.assert_array_equal(audio, samples)
        assert audio.flags.writeable
        command = run.call_args.args[0]
        assert command[command.index("-ar") + 1] == "16000"
        assert command[command.index("-f") + 1] == "f32le"


# ===================================================================
# Transcriber on the whisper.cpp backend
# ===================================================================


class _FakeEngine:
    """Simulates pywhispercpp's Model through the ``_whispercpp.run`` adapter."""

    def __init__(self, segments=((0.0, 4.0, " Hello world"), (4.0, 10.0, " Bye"))):
        self.segments = segments
        self.calls = []


def _fake_run(engine, audio, *, language, beam_size, vad_model, on_segment, should_abort):
    engine.calls.append(dict(language=language, beam_size=beam_size, vad_model=vad_model))
    for start, end, text in engine.segments:
        if should_abort():
            return
        on_segment(start, end, text)


@pytest.fixture()
def whispercpp_env(silent_wav, models_dir):
    """Patch the native/ffmpeg edges of ``_whispercpp`` with fakes."""
    engine = _FakeEngine()
    with patch.object(wcpp, "is_downloaded", return_value=True), \
            patch.object(wcpp, "ensure_downloaded", return_value=Path("vad.bin")) as dl, \
            patch.object(wcpp, "load_model", return_value=engine) as load, \
            patch.object(wcpp, "load_audio", return_value=np.zeros(16000 * 10, np.float32)), \
            patch.object(wcpp, "detect_language", return_value=("pt", 0.9)), \
            patch.object(wcpp, "supports_vad", return_value=True), \
            patch.object(wcpp, "run", side_effect=_fake_run):
        yield dict(engine=engine, ensure_downloaded=dl, load_model=load, audio=silent_wav)


class TestWhisperCppTranscription:
    def test_transcribe_success(self, whispercpp_env):
        progress = []
        result = Transcriber(backend=WHISPER_CPP).transcribe(
            str(whispercpp_env["audio"]),
            model="tiny",
            progress_callback=lambda f, m: progress.append((f, m)),
        )

        assert [s.text for s in result.segments] == ["Hello world", "Bye"]
        assert result.duration == pytest.approx(10.0)
        assert result.language == "pt"
        assert result.language_probability == pytest.approx(0.9)
        assert progress[0][0] == 0.0 and progress[-1] == (1.0, "Done.")
        fractions = [f for f, _ in progress]
        assert fractions == sorted(fractions)
        call = whispercpp_env["engine"].calls[0]
        assert call == dict(language="pt", beam_size=5, vad_model=Path("vad.bin"))

    def test_explicit_language_skips_detection(self, whispercpp_env):
        with patch.object(wcpp, "detect_language") as detect:
            result = Transcriber(backend=WHISPER_CPP).transcribe(
                str(whispercpp_env["audio"]), model="tiny", language="en"
            )
        detect.assert_not_called()
        assert result.language == "en"
        assert result.language_probability is None

    def test_model_reused_between_files(self, whispercpp_env):
        t = Transcriber(backend=WHISPER_CPP)
        t.transcribe(str(whispercpp_env["audio"]), model="tiny")
        t.transcribe(str(whispercpp_env["audio"]), model="tiny")
        t.transcribe(str(whispercpp_env["audio"]), model="base")
        assert whispercpp_env["load_model"].call_count == 2

    def test_vad_disabled(self, whispercpp_env):
        Transcriber(backend=WHISPER_CPP).transcribe(
            str(whispercpp_env["audio"]), model="tiny", vad_filter=False
        )
        whispercpp_env["ensure_downloaded"].assert_not_called()
        assert whispercpp_env["engine"].calls[0]["vad_model"] is None

    def test_old_bindings_skip_vad(self, whispercpp_env):
        with patch.object(wcpp, "supports_vad", return_value=False):
            result = Transcriber(backend=WHISPER_CPP).transcribe(
                str(whispercpp_env["audio"]), model="tiny"
            )
        whispercpp_env["ensure_downloaded"].assert_not_called()
        assert len(result.segments) == 2

    def test_vad_download_failure_falls_back(self, whispercpp_env):
        whispercpp_env["ensure_downloaded"].side_effect = OSError("offline")
        result = Transcriber(backend=WHISPER_CPP).transcribe(
            str(whispercpp_env["audio"]), model="tiny"
        )
        assert len(result.segments) == 2
        assert whispercpp_env["engine"].calls[0]["vad_model"] is None

    def test_cancel_during_decoding(self, whispercpp_env):
        cancel = threading.Event()

        def progress(fraction, message):
            if fraction > 0.1:  # first segment decoded
                cancel.set()

        with pytest.raises(TranscriptionCancelled):
            Transcriber(backend=WHISPER_CPP).transcribe(
                str(whispercpp_env["audio"]),
                model="tiny",
                progress_callback=progress,
                cancel_event=cancel,
            )

    def test_downloads_missing_model_with_progress(self, whispercpp_env):
        def fake_download(spec, progress=None, check_cancel=None):
            if progress is not None:
                progress((spec.size + 1) // 2, spec.size)  # just over half
                progress(spec.size, spec.size)
            return Path(spec.filename)

        messages = []
        whispercpp_env["ensure_downloaded"].side_effect = fake_download
        with patch.object(wcpp, "is_downloaded", return_value=False):
            Transcriber(backend=WHISPER_CPP).transcribe(
                str(whispercpp_env["audio"]),
                model="tiny",
                progress_callback=lambda f, m: messages.append(m),
            )
        assert any("first time setup" in m for m in messages)
        assert any("50%" in m for m in messages)
        assert any("100%" in m for m in messages)

    def test_unsupported_model(self, whispercpp_env):
        with pytest.raises(ValueError, match="not available with the whisper.cpp"):
            Transcriber(backend=WHISPER_CPP).transcribe(
                str(whispercpp_env["audio"]), model="distil-large-v3"
            )

    def test_errors_are_not_retried_as_gpu_failures(self, whispercpp_env):
        whispercpp_env["load_model"].side_effect = RuntimeError("cuda init failed")
        with pytest.raises(RuntimeError, match="cuda init failed"):
            Transcriber(backend=WHISPER_CPP).transcribe(
                str(whispercpp_env["audio"]), model="tiny", device="auto"
            )
        assert whispercpp_env["load_model"].call_count == 1


class _Model15:
    """pywhispercpp 1.5 surface: abort callback and VAD parameters."""

    def __init__(self, segments=((150, 420, " hi"),)):
        self.segments = segments
        self.params = None

    @staticmethod
    def get_params_schema():
        return {"language": {}, "vad": {}, "vad_model_path": {}}

    def transcribe(self, media, n_processors=None, new_segment_callback=None,
                   abort_callback=None, extract_probability=False, **params):
        self.params = dict(params, abort_callback=abort_callback)
        for t0, t1, text in self.segments:
            new_segment_callback(MagicMock(t0=t0, t1=t1, text=text))
        return []


class _Model14:
    """pywhispercpp 1.4 surface (Fedora 44): no abort callback, no VAD."""

    def __init__(self):
        self.params = None

    @staticmethod
    def get_params_schema():
        return {"language": {}}

    def transcribe(self, media, n_processors=None, new_segment_callback=None, **params):
        self.params = params
        return []


class TestRunAdapter:
    def test_capability_detection(self):
        assert wcpp.supports_abort(_Model15()) and wcpp.supports_vad(_Model15())
        assert not wcpp.supports_abort(_Model14())
        assert not wcpp.supports_vad(_Model14())

    def test_maps_parameters_and_segments(self):
        model = _Model15()
        seen = []

        def abort():
            return False

        wcpp.run(
            model,
            "AUDIO",
            language="en",
            beam_size=5,
            vad_model=Path("/m/vad.bin"),
            on_segment=lambda s, e, t: seen.append((s, e, t)),
            should_abort=abort,
        )
        assert seen == [(1.5, 4.2, " hi")]
        assert model.params == {
            "language": "en",
            "vad": True,
            "vad_model_path": str(Path("/m/vad.bin")),
            "beam_search": {"beam_size": 5, "patience": -1.0},
            "abort_callback": abort,
        }

    def test_greedy_without_vad(self):
        model = _Model15(segments=())
        wcpp.run(
            model, "AUDIO", language="en", beam_size=1, vad_model=None,
            on_segment=lambda *a: None, should_abort=lambda: False,
        )
        assert model.params["vad"] is False
        assert "beam_search" not in model.params
        assert "vad_model_path" not in model.params

    def test_old_bindings_get_only_supported_params(self):
        model = _Model14()
        wcpp.run(
            model, "AUDIO", language="en", beam_size=5, vad_model=None,
            on_segment=lambda *a: None, should_abort=lambda: False,
        )
        assert model.params == {
            "language": "en",
            "beam_search": {"beam_size": 5, "patience": -1.0},
        }


# ===================================================================
# CLI validation per backend
# ===================================================================


class TestCliBackend:
    def test_backend_flag(self):
        args = _parse_args(["a.mp3", "--backend", "whisper.cpp", "--model", "tiny"])
        assert args.backend == WHISPER_CPP

    def test_backend_defaults_to_detected(self):
        assert _parse_args(["a.mp3"]).backend == FASTER_WHISPER

    def test_whispercpp_only_model_accepted(self):
        args = _parse_args(
            ["a.mp3", "--backend", "whisper.cpp", "--model", "large-v3-turbo-q5_0"]
        )
        assert args.model == "large-v3-turbo-q5_0"

    @pytest.mark.parametrize(
        "extra",
        [
            ["--model", "distil-large-v3"],
            ["--device", "cuda"],
            ["--compute", "int8"],
            ["--benchmark", "--models", "tiny", "distil-large-v3"],
        ],
    )
    def test_rejects_options_backend_cannot_honor(self, extra, capsys):
        with pytest.raises(SystemExit):
            _parse_args(["a.mp3", "--backend", "whisper.cpp", *extra])
        assert "not supported by the whisper.cpp backend" in capsys.readouterr().err

    def test_rejects_whispercpp_model_on_faster_whisper(self):
        with pytest.raises(SystemExit):
            _parse_args(["a.mp3", "--model", "large-v3-turbo-q5_0"])
