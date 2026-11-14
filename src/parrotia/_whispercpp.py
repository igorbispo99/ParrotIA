"""whisper.cpp backend, used where faster-whisper is unavailable (e.g. Fedora).

Fedora ships whisper.cpp and its Python bindings (``python3-pywhispercpp``)
but not faster-whisper/CTranslate2/PyAV, so the native Fedora package runs
transcription through this module instead. It is imported lazily by
:mod:`parrotia.transcriber`; nothing here imports ``pywhispercpp`` or NumPy at
module load time, so the model tables are usable without either installed.

Model files are fetched by ParrotIA itself rather than pywhispercpp's helper so
downloads are pinned to an exact repository revision, verified by SHA-256,
written atomically (a ``.part`` file renamed on success) and resumable.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

SAMPLE_RATE = 16000

# Language detection only needs the opening window Whisper itself sees.
_LANGUAGE_PROBE_SECONDS = 30

_CHUNK_SIZE = 1 << 20  # 1 MiB


@dataclass(frozen=True)
class ModelFile:
    """A single downloadable model file, pinned to an exact revision."""

    repo: str
    revision: str
    filename: str
    size: int
    sha256: str

    @property
    def url(self) -> str:
        return f"https://huggingface.co/{self.repo}/resolve/{self.revision}/{self.filename}"


# GGML conversions of OpenAI's Whisper weights published by the whisper.cpp
# project (model card license: MIT). Sizes/hashes are the repository's LFS
# metadata at the pinned revision; bump revision, size and hash together.
_WHISPER_REPO = "ggerganov/whisper.cpp"
_WHISPER_REVISION = "5359861c739e955e79d9a303bcbc70fb988958b1"


def _whisper_file(filename: str, size: int, sha256: str) -> ModelFile:
    return ModelFile(_WHISPER_REPO, _WHISPER_REVISION, filename, size, sha256)


MODEL_FILES: Dict[str, ModelFile] = {
    "tiny": _whisper_file(
        "ggml-tiny.bin",
        77691713,
        "be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21",
    ),
    "base": _whisper_file(
        "ggml-base.bin",
        147951465,
        "60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe",
    ),
    "small": _whisper_file(
        "ggml-small.bin",
        487601967,
        "1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b",
    ),
    "medium": _whisper_file(
        "ggml-medium.bin",
        1533763059,
        "6c14d5adee5f86394037b4e4e8b59f1673b6cee10e3cf0b11bbdbee79c156208",
    ),
    "large-v3": _whisper_file(
        "ggml-large-v3.bin",
        3095033483,
        "64d182b440b98d5203c4f9bd541544d84c605196c4f7b845dfa11fb23594d1e2",
    ),
    "large-v3-turbo": _whisper_file(
        "ggml-large-v3-turbo.bin",
        1624555275,
        "1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69",
    ),
    # 5-bit quantized turbo: about a third of the size and noticeably faster
    # on CPU, at a small accuracy cost.
    "large-v3-turbo-q5_0": _whisper_file(
        "ggml-large-v3-turbo-q5_0.bin",
        574041195,
        "394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2",
    ),
}

# Silero VAD converted to GGML by the ggml project (model card license: MIT).
VAD_MODEL = ModelFile(
    "ggml-org/whisper-vad",
    "9ffd54a1e1ee413ddf265af9913beaf518d1639b",
    "ggml-silero-v5.1.2.bin",
    885098,
    "29940d98d42b91fbd05ce489f3ecf7c72f0a42f027e4875919a28fb4c04ea2cf",
)

AVAILABLE_MODELS: List[str] = list(MODEL_FILES)


def human_size(num_bytes: int) -> str:
    """Approximate, UI-friendly size: ``1624555275`` -> ``"~1.6 GB"``."""
    if num_bytes >= 10**9:
        return f"~{num_bytes / 10**9:.1f} GB"
    return f"~{round(num_bytes / 10**6)} MB"


MODEL_SIZES: Dict[str, str] = {
    name: human_size(spec.size) for name, spec in MODEL_FILES.items()
}


def models_dir() -> Path:
    """Directory holding downloaded GGML models.

    ``PARROTIA_MODELS_DIR`` overrides it (e.g. a shared, pre-populated folder
    for offline machines); otherwise the per-user data directory is used.
    """
    override = os.environ.get("PARROTIA_MODELS_DIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "parrotia" / "models"


def model_path(spec: ModelFile) -> Path:
    return models_dir() / spec.filename


def is_downloaded(spec: ModelFile) -> bool:
    """True only for a complete file; a partial ``.part`` download is not."""
    try:
        return model_path(spec).stat().st_size == spec.size
    except OSError:
        return False


# (bytes_done, bytes_total)
DownloadProgress = Callable[[int, int], None]


def _hash_existing(path: Path) -> "hashlib._Hash":
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest


def ensure_downloaded(
    spec: ModelFile,
    progress: Optional[DownloadProgress] = None,
    check_cancel: Optional[Callable[[], None]] = None,
) -> Path:
    """Return the local path of ``spec``, downloading it first if needed.

    An interrupted download resumes from its ``.part`` file. The finished file
    must match the pinned size and SHA-256 before it replaces the target, so a
    truncated or tampered download is never mistaken for a cached model.
    ``check_cancel`` is called between chunks and may raise to abort; the
    partial file is kept so a retry resumes.
    """
    target = model_path(spec)
    if is_downloaded(spec):
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")

    done = part.stat().st_size if part.exists() else 0
    if done > spec.size:
        part.unlink()
        done = 0
    digest = _hash_existing(part) if done else hashlib.sha256()

    if done < spec.size:
        request = urllib.request.Request(spec.url, headers={"User-Agent": "ParrotIA"})
        if done:
            request.add_header("Range", f"bytes={done}-")
        with urllib.request.urlopen(request, timeout=60) as response:
            if done and response.status != 206:
                # Server ignored the range request: start over.
                done = 0
                digest = hashlib.sha256()
            with open(part, "ab" if done else "wb") as out:
                while True:
                    if check_cancel is not None:
                        check_cancel()
                    chunk = response.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    out.write(chunk)
                    digest.update(chunk)
                    done += len(chunk)
                    if progress is not None:
                        progress(done, spec.size)

    if done != spec.size or digest.hexdigest() != spec.sha256:
        part.unlink(missing_ok=True)
        raise RuntimeError(
            f"Download of {spec.filename} failed verification "
            f"(got {done} of {spec.size} bytes or a checksum mismatch). Please retry."
        )
    os.replace(part, target)
    return target


def load_audio(path: str):
    """Decode any ffmpeg-readable media file to 16 kHz mono float32 samples."""
    import numpy as np

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError(
            "ffmpeg is required to decode audio but was not found on PATH. "
            "Install it (on Fedora: sudo dnf install ffmpeg-free)."
        )
    proc = subprocess.run(
        [
            ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
            "-i", path,
            "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-",
        ],
        capture_output=True,
    )
    if proc.returncode != 0:
        lines = proc.stderr.decode("utf-8", errors="replace").strip().splitlines()
        reason = lines[-1] if lines else f"exit code {proc.returncode}"
        raise RuntimeError(f"Could not decode {Path(path).name}: {reason}")
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


def _thread_count() -> int:
    return max(1, min(8, os.cpu_count() or 4))


def load_model(path: Path, beam_size: int):
    """Create a pywhispercpp model for the GGML file at ``path``."""
    from pywhispercpp.model import Model  # imported lazily: native extension

    return Model(
        str(path),
        # Silence whisper.cpp's verbose native logging on stderr.
        redirect_whispercpp_logs_to=None,
        params_sampling_strategy=1 if beam_size > 1 else 0,
        n_threads=_thread_count(),
        print_progress=False,
        print_realtime=False,
    )


def detect_language(model, audio):
    """Return ``(language_code, probability)`` for the opening of ``audio``."""
    (code, probability), _ = model.auto_detect_language(
        audio[: SAMPLE_RATE * _LANGUAGE_PROBE_SECONDS], n_threads=_thread_count()
    )
    return code, float(probability)


def _explicit_parameters(func) -> "set[str]":
    import inspect

    try:
        return set(inspect.signature(func).parameters)
    except (TypeError, ValueError):
        return set()


def supports_abort(model) -> bool:
    """pywhispercpp >= 1.5 can stop a decode early (Fedora 44 ships 1.4)."""
    return "abort_callback" in _explicit_parameters(model.transcribe)


def supports_vad(model) -> bool:
    """pywhispercpp >= 1.5 exposes whisper.cpp's VAD parameters."""
    schema = getattr(model, "get_params_schema", None)
    try:
        return callable(schema) and "vad" in schema()
    except Exception:
        return False


def run(
    model,
    audio,
    *,
    language: str,
    beam_size: int,
    vad_model: Optional[Path],
    on_segment: Callable[[float, float, str], None],
    should_abort: Callable[[], bool],
) -> None:
    """Transcribe ``audio``; each segment is passed to ``on_segment``.

    Segments are delivered as they are decoded (start/end in seconds), which
    is what lets the caller stream progress. ``should_abort`` is polled by
    whisper.cpp and stops decoding early when it returns True; bindings too old
    to support that finish the current decode first. ``vad_model`` must be None
    unless :func:`supports_vad` is true.
    """
    params: dict = dict(language=language)
    if beam_size > 1:
        params["beam_search"] = {"beam_size": beam_size, "patience": -1.0}
    if supports_vad(model):
        params["vad"] = vad_model is not None
        if vad_model is not None:
            params["vad_model_path"] = str(vad_model)
    if supports_abort(model):
        params["abort_callback"] = should_abort

    def segment_callback(segment) -> None:
        on_segment(segment.t0 / 100.0, segment.t1 / 100.0, segment.text)

    model.transcribe(audio, new_segment_callback=segment_callback, **params)
