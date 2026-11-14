"""Transcription engine wrapping faster-whisper (CTranslate2) or whisper.cpp.

The module is deliberately UI-agnostic: it exposes a small dataclass result and
a :class:`Transcriber` that loads models lazily, caches them, reports progress
through a callback, and supports cooperative cancellation. The GUI imports this;
it could equally be driven from a script or a test.

Two inference backends are supported. faster-whisper is the default wherever it
is installed (pip, Windows/Linux installers). whisper.cpp, through
``pywhispercpp``, is used where faster-whisper is unavailable — notably the
native Fedora package. ``PARROTIA_BACKEND`` forces a choice.
"""

from __future__ import annotations

import glob
import importlib.util
import os
import site
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

# On Windows with CUDA, multiple packages (CTranslate2, PyTorch/MKL, NVIDIA
# wheels) can each ship their own copy of the Intel OpenMP runtime
# (libiomp5md.dll).  Loading two copies causes a fatal C-level abort:
#   "OMP: Error #15: Initializing libiomp5md.dll, but found libiomp5md.dll
#    already initialized."
# Setting this *before* any native library is imported tells the runtime to
# tolerate the duplicate and keeps the process alive.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# State-of-the-art, fully local and free Whisper variants. ``turbo`` and the
# distil models trade a sliver of accuracy for large speedups; large-v3 is the
# most accurate.
AVAILABLE_MODELS: List[str] = [
    "tiny",
    "base",
    "small",
    "medium",
    "large-v3",
    "large-v3-turbo",
    "distil-large-v3",
]

DEFAULT_MODEL = "large-v3-turbo"

# Friendly name -> Whisper language code. ``None`` means auto-detect.
LANGUAGES: "dict[str, Optional[str]]" = {
    "Auto detect": None,
    "English": "en",
    "Spanish": "es",
    "Portuguese": "pt",
    "French": "fr",
    "German": "de",
    "Italian": "it",
    "Dutch": "nl",
    "Russian": "ru",
    "Ukrainian": "uk",
    "Polish": "pl",
    "Turkish": "tr",
    "Arabic": "ar",
    "Hebrew": "he",
    "Hindi": "hi",
    "Chinese": "zh",
    "Japanese": "ja",
    "Korean": "ko",
}

DEVICES = ["auto", "cuda", "cpu"]
COMPUTE_TYPES = ["auto", "int8", "int8_float16", "float16", "float32"]

# Audio/video containers PyAV (bundled with faster-whisper) can decode.
SUPPORTED_EXTENSIONS = [
    ".mp3",
    ".wav",
    ".m4a",
    ".ogg",
    ".oga",
    ".opus",
    ".flac",
    ".aac",
    ".wma",
    ".mp4",
    ".mkv",
    ".mov",
    ".avi",
    ".webm",
]

# HuggingFace repo IDs used by faster-whisper for each model.
_MODEL_REPOS: dict[str, str] = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
    "large-v3": "Systran/faster-whisper-large-v3",
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    "distil-large-v3": "Systran/faster-distil-whisper-large-v3",
}

# Approximate download sizes (informational, shown in the UI).
MODEL_SIZES: dict[str, str] = {
    "tiny": "~75 MB",
    "base": "~145 MB",
    "small": "~465 MB",
    "medium": "~1.5 GB",
    "large-v3": "~3.1 GB",
    "large-v3-turbo": "~1.6 GB",
    "distil-large-v3": "~1.5 GB",
}

FASTER_WHISPER = "faster-whisper"
WHISPER_CPP = "whisper.cpp"
BACKENDS: List[str] = [FASTER_WHISPER, WHISPER_CPP]


@dataclass(frozen=True)
class BackendOptions:
    """The choices a UI should offer for one inference backend."""

    name: str
    models: List[str]
    model_sizes: Dict[str, str]
    devices: List[str]
    compute_types: List[str]
    default_model: str = DEFAULT_MODEL


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def detect_backend() -> str:
    """Pick the inference backend: ``PARROTIA_BACKEND``, else what's installed.

    faster-whisper wins when both are installed. If neither is, faster-whisper
    is returned so the eventual import error names the default dependency.
    """
    requested = os.environ.get("PARROTIA_BACKEND", "").strip().lower()
    if requested:
        if requested not in BACKENDS:
            raise ValueError(
                f"PARROTIA_BACKEND={requested!r} is not one of: {', '.join(BACKENDS)}"
            )
        return requested
    if _module_available("faster_whisper"):
        return FASTER_WHISPER
    if _module_available("pywhispercpp"):
        return WHISPER_CPP
    return FASTER_WHISPER


def backend_options(backend: Optional[str] = None) -> BackendOptions:
    """Models/devices/compute types valid for ``backend`` (default: detected).

    The module-level ``AVAILABLE_MODELS``/``DEVICES``/``COMPUTE_TYPES`` describe
    the faster-whisper backend; front-ends should prefer this function.
    """
    backend = backend or detect_backend()
    if backend == WHISPER_CPP:
        from . import _whispercpp

        return BackendOptions(
            name=WHISPER_CPP,
            models=list(_whispercpp.AVAILABLE_MODELS),
            model_sizes=dict(_whispercpp.MODEL_SIZES),
            # whisper.cpp runs on the CPU here; precision is fixed by the model file.
            devices=["auto", "cpu"],
            compute_types=["auto"],
        )
    if backend == FASTER_WHISPER:
        return BackendOptions(
            name=FASTER_WHISPER,
            models=list(AVAILABLE_MODELS),
            model_sizes=dict(MODEL_SIZES),
            devices=list(DEVICES),
            compute_types=list(COMPUTE_TYPES),
        )
    raise ValueError(f"Unknown backend {backend!r}; expected one of: {', '.join(BACKENDS)}")


@dataclass
class Segment:
    start: float
    end: float
    text: str


@dataclass
class TranscriptionResult:
    source_name: str
    model: str
    language: str
    duration: float
    segments: List[Segment] = field(default_factory=list)
    language_probability: Optional[float] = None


class TranscriptionCancelled(Exception):
    """Raised when a caller cancels an in-flight transcription."""


# Progress callback: (fraction_complete in 0..1, human-readable status message).
ProgressCallback = Callable[[float, str], None]


def _resolve_compute_type(device: str, compute_type: str) -> str:
    """Pick a sensible compute type when the user leaves it on ``auto``."""
    if compute_type != "auto":
        return compute_type
    return "float16" if device == "cuda" else "int8"


def _register_cuda_dll_dirs() -> None:
    """Make CUDA libs shipped as pip wheels discoverable to CTranslate2.

    On Windows, ``nvidia-cublas-cu12`` / ``nvidia-cudnn-cu12`` install their
    DLLs under ``site-packages/nvidia/*/bin``. CTranslate2 won't find them
    unless those directories are on the DLL search path. Best-effort and silent.
    """
    if os.name != "nt":
        return
    roots = list(site.getsitepackages())
    user_site = site.getusersitepackages()
    if isinstance(user_site, str):
        roots.append(user_site)
    extra_path = []
    for root in roots:
        for bin_dir in glob.glob(os.path.join(root, "nvidia", "*", "bin")):
            try:
                os.add_dll_directory(bin_dir)
            except (OSError, AttributeError):
                pass
            extra_path.append(bin_dir)
    # CTranslate2 loads cuBLAS/cuDNN by bare name, which doesn't reliably honor
    # add_dll_directory; prepending to PATH makes the standard DLL search find
    # them (and their inter-dependencies) too.
    if extra_path:
        os.environ["PATH"] = os.pathsep.join(extra_path + [os.environ.get("PATH", "")])


_register_cuda_dll_dirs()


_CUDA_ERROR_HINTS = ("cublas", "cudnn", "cuda", "cannot be loaded", "libcu", "gpu")


def _is_cuda_error(exc: Exception) -> bool:
    """Heuristic: did this failure come from a missing/broken CUDA backend?"""
    message = str(exc).lower()
    return any(hint in message for hint in _CUDA_ERROR_HINTS)


class Transcriber:
    """Loads and caches Whisper models and runs transcriptions.

    A single instance can be reused across files; switching model/device only
    reloads when the combination actually changes.
    """

    def __init__(self, backend: Optional[str] = None) -> None:
        self.backend = backend or detect_backend()
        if self.backend not in BACKENDS:
            raise ValueError(
                f"Unknown backend {self.backend!r}; expected one of: {', '.join(BACKENDS)}"
            )
        self._model = None
        self._model_key: Optional[tuple] = None
        self._lock = threading.Lock()

    @staticmethod
    def is_model_cached(model_name: str, backend: Optional[str] = None) -> bool:
        """Return True if the model files are already downloaded locally."""
        if (backend or detect_backend()) == WHISPER_CPP:
            from . import _whispercpp

            spec = _whispercpp.MODEL_FILES.get(model_name)
            return spec is None or _whispercpp.is_downloaded(spec)
        repo_id = _MODEL_REPOS.get(model_name)
        if repo_id is None:
            return True  # custom path or unknown model — assume available
        try:
            from huggingface_hub.constants import HF_HUB_CACHE

            repo_dir = os.path.join(
                HF_HUB_CACHE, "models--" + repo_id.replace("/", "--")
            )
            snapshots = os.path.join(repo_dir, "snapshots")
            return os.path.isdir(snapshots) and len(os.listdir(snapshots)) > 0
        except Exception:
            return True  # can't check — assume cached to avoid false alarms

    def _load_model(self, model: str, device: str, compute_type: str):
        from faster_whisper import WhisperModel  # imported lazily: heavy

        resolved_device = device
        resolved_compute = _resolve_compute_type(device, compute_type)
        key = (model, resolved_device, resolved_compute)

        with self._lock:
            if key == self._model_key and self._model is not None:
                return self._model

            try:
                self._model = WhisperModel(
                    model, device=resolved_device, compute_type=resolved_compute
                )
            except Exception:
                # GPU unavailable / driver mismatch / unsupported compute type:
                # fall back to a CPU configuration that always works.
                if resolved_device != "cpu":
                    self._model = WhisperModel(model, device="cpu", compute_type="int8")
                    key = (model, "cpu", "int8")
                else:
                    raise
            self._model_key = key
            return self._model

    def transcribe(
        self,
        audio_path: str,
        *,
        model: str = DEFAULT_MODEL,
        language: Optional[str] = None,
        device: str = "auto",
        compute_type: str = "auto",
        beam_size: int = 5,
        vad_filter: bool = True,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> TranscriptionResult:
        """Transcribe ``audio_path`` and return a :class:`TranscriptionResult`.

        ``progress_callback`` is called with a 0..1 fraction and a status
        string. If ``cancel_event`` is set during processing,
        :class:`TranscriptionCancelled` is raised.
        """
        path = Path(audio_path)
        if not path.is_file():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        def report(fraction: float, message: str) -> None:
            if progress_callback is not None:
                progress_callback(max(0.0, min(1.0, fraction)), message)

        def check_cancel() -> None:
            if cancel_event is not None and cancel_event.is_set():
                raise TranscriptionCancelled()

        try:
            return self._transcribe_once(
                path,
                model,
                language,
                device,
                compute_type,
                beam_size,
                vad_filter,
                report,
                check_cancel,
            )
        except TranscriptionCancelled:
            raise
        except Exception as exc:
            # CTranslate2 can fail lazily — the missing-cuBLAS/cuDNN DLL only
            # surfaces once decoding actually touches the GPU. If the GPU path
            # breaks, transparently restart the whole run on CPU.
            if (
                self.backend == FASTER_WHISPER
                and device != "cpu"
                and _is_cuda_error(exc)
            ):
                report(0.0, "GPU unavailable — falling back to CPU…")
                self._model = None
                self._model_key = None
                return self._transcribe_once(
                    path,
                    model,
                    language,
                    "cpu",
                    "int8",
                    beam_size,
                    vad_filter,
                    report,
                    check_cancel,
                )
            raise

    def _transcribe_once(
        self,
        path: Path,
        model: str,
        language: Optional[str],
        device: str,
        compute_type: str,
        beam_size: int,
        vad_filter: bool,
        report,
        check_cancel,
    ) -> TranscriptionResult:
        if self.backend == WHISPER_CPP:
            return self._transcribe_whispercpp(
                path, model, language, beam_size, vad_filter, report, check_cancel
            )
        downloading = not self.is_model_cached(model, FASTER_WHISPER)
        if downloading:
            size = MODEL_SIZES.get(model, "")
            hint = f" ({size})" if size else ""
            report(
                0.0,
                f"📥 Downloading model '{model}'{hint} — first time setup, please wait…",
            )
        else:
            report(0.0, f"Loading model '{model}'…")
        check_cancel()
        whisper = self._load_model(model, device, compute_type)

        report(0.05, "Analyzing audio…")
        check_cancel()
        segments_iter, info = whisper.transcribe(
            str(path),
            language=language,
            beam_size=beam_size,
            vad_filter=vad_filter,
        )

        duration = float(getattr(info, "duration", 0.0) or 0.0)
        detected_language = getattr(info, "language", None) or (language or "unknown")
        language_probability = getattr(info, "language_probability", None)

        report(
            0.1,
            f"Transcribing ({detected_language})…",
        )

        segments: List[Segment] = []
        # faster-whisper yields segments lazily as decoding proceeds; iterating
        # is where the real work happens, which lets us stream progress.
        for segment in segments_iter:
            check_cancel()
            text = segment.text.strip()
            if text:
                segments.append(Segment(segment.start, segment.end, text))
            if duration > 0:
                report(0.1 + 0.9 * (segment.end / duration), "Transcribing…")

        report(1.0, "Done.")
        return TranscriptionResult(
            source_name=path.name,
            model=model,
            language=detected_language,
            duration=duration,
            segments=segments,
            language_probability=language_probability,
        )

    # ------------------------------------------------------- whisper.cpp ---
    def _load_whispercpp(self, model: str, beam_size: int):
        from . import _whispercpp

        # Beam search vs greedy is fixed when the whisper.cpp model is created.
        key = (WHISPER_CPP, model, beam_size > 1)
        with self._lock:
            if key == self._model_key and self._model is not None:
                return self._model
            path = _whispercpp.model_path(_whispercpp.MODEL_FILES[model])
            self._model = _whispercpp.load_model(path, beam_size)
            self._model_key = key
            return self._model

    def _transcribe_whispercpp(
        self,
        path: Path,
        model: str,
        language: Optional[str],
        beam_size: int,
        vad_filter: bool,
        report,
        check_cancel,
    ) -> TranscriptionResult:
        from . import _whispercpp

        spec = _whispercpp.MODEL_FILES.get(model)
        if spec is None:
            raise ValueError(
                f"Model '{model}' is not available with the whisper.cpp backend. "
                f"Choose one of: {', '.join(_whispercpp.AVAILABLE_MODELS)}"
            )

        if not _whispercpp.is_downloaded(spec):
            size = _whispercpp.MODEL_SIZES[model]
            report(
                0.0,
                f"📥 Downloading model '{model}' ({size}) — first time setup, please wait…",
            )
            last_percent = [-1]

            def on_download(done: int, total: int) -> None:
                percent = int(100 * done / total) if total else 0
                if percent != last_percent[0]:  # throttle UI updates to 1% steps
                    last_percent[0] = percent
                    report(0.0, f"📥 Downloading model '{model}' — {percent}% of {size}…")

            _whispercpp.ensure_downloaded(spec, on_download, check_cancel)

        report(0.0, f"Loading model '{model}'…")
        check_cancel()
        whisper = self._load_whispercpp(model, beam_size)

        vad_model: Optional[Path] = None
        if vad_filter and _whispercpp.supports_vad(whisper):
            try:
                vad_model = _whispercpp.ensure_downloaded(
                    _whispercpp.VAD_MODEL, None, check_cancel
                )
            except TranscriptionCancelled:
                raise
            except Exception:
                # VAD only skips silence; transcribe the whole file without it.
                vad_model = None

        report(0.05, "Analyzing audio…")
        check_cancel()
        audio = _whispercpp.load_audio(str(path))
        duration = len(audio) / _whispercpp.SAMPLE_RATE

        language_probability: Optional[float] = None
        if language:
            detected_language = language
        else:
            detected_language, language_probability = _whispercpp.detect_language(
                whisper, audio
            )

        report(0.1, f"Transcribing ({detected_language})…")
        check_cancel()

        segments: List[Segment] = []

        def on_segment(start: float, end: float, text: str) -> None:
            text = text.strip()
            if text:
                segments.append(Segment(start, end, text))
            if duration > 0:
                report(0.1 + 0.9 * min(1.0, end / duration), "Transcribing…")

        def should_abort() -> bool:
            try:
                check_cancel()
            except TranscriptionCancelled:
                return True
            return False

        _whispercpp.run(
            whisper,
            audio,
            language=detected_language,
            beam_size=beam_size,
            vad_model=vad_model,
            on_segment=on_segment,
            should_abort=should_abort,
        )
        check_cancel()  # an aborted decode returns normally with partial output

        report(1.0, "Done.")
        return TranscriptionResult(
            source_name=path.name,
            model=model,
            language=detected_language,
            duration=duration,
            segments=segments,
            language_probability=language_probability,
        )
