"""Standalone desktop executable: the GUI or Windows Explorer's queue."""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path


def _smoke_test(report: Path) -> None:
    """Exercise native dependencies and Tk without downloading a model."""
    import io
    import tkinter
    import wave

    import av
    import customtkinter

    from parrotia import __version__
    from parrotia.app import TranscriberApp

    stream = io.BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * 1600)
    stream.seek(0)
    details = {}
    if sys.platform == "darwin":
        import tempfile
        import _pywhispercpp as native
        from pywhispercpp.model import Model
        from parrotia._audio import decode_audio
        from parrotia.transcriber import detect_backend

        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "test.wav"
            wav.write_bytes(stream.getvalue())
            samples = decode_audio(str(wav))
        details.update(
            backend=detect_backend(),
            gpu_supported="MTL" in str(native.whisper_print_system_info()),
        )
        Model.system_info()  # Exercise the native library without a model download.
        model_path = os.environ.get("PARROTIA_SMOKE_MODEL")
        if model_path:
            from parrotia import _whispercpp
            from parrotia.transcriber import metal_available

            audio_path = os.environ.get("PARROTIA_SMOKE_AUDIO")
            speech = decode_audio(audio_path) if audio_path else samples
            devices = ["cpu", "metal"] if metal_available() else ["cpu"]
            details["inference"] = {}
            for device in devices:
                model = _whispercpp.load_model(Path(model_path), 1, device=device)
                segments = model.transcribe(speech, language="en")
                details["inference"][device] = " ".join(s.text for s in segments)
                _whispercpp.release_model(model)
                del model
    else:
        import ctranslate2
        import tokenizers
        from faster_whisper.audio import decode_audio
        from faster_whisper.vad import get_vad_model

        samples = decode_audio(stream)
        get_vad_model()
        details.update(
            ctranslate2=ctranslate2.__version__, tokenizers=tokenizers.__version__
        )
    app = TranscriberApp()
    app.withdraw()
    app.update()
    app.destroy()
    report.write_text(
        json.dumps(
            {
                "version": __version__,
                "samples": len(samples),
                "av": av.__version__,
                "customtkinter": customtkinter.__version__,
                "tk": tkinter.TkVersion,
                **details,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _ensure_console_streams() -> None:
    # Windowed executables have no console streams. Native dependency startup
    # warnings still write to them, so provide valid sinks before any imports.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115 -- process lifetime
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115 -- process lifetime


def main() -> int:
    _ensure_console_streams()
    # Pin taskbar identity to our executable and icon, rather than python.exe.
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "ParrotIA.Desktop"
        )
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
            _smoke_test(Path(sys.argv[2]))
        elif len(sys.argv) == 4 and sys.argv[1] == "--lifecycle-smoke-test":
            from lifecycle_smoke import run

            run(Path(sys.argv[2]), sys.argv[3])
        elif len(sys.argv) > 1 and sys.argv[1] == "--shell":
            from parrotia.explorer import main as explorer_main

            return explorer_main(sys.argv[2:])
        else:
            from parrotia.app import main as gui_main

            gui_main()
    except Exception:  # noqa: BLE001 -- surface startup errors from any dependency
        detail = traceback.format_exc()
        print(detail, file=sys.stderr)
        if len(sys.argv) >= 3 and sys.argv[1] in (
            "--smoke-test",
            "--lifecycle-smoke-test",
        ):
            Path(sys.argv[2]).write_text(detail, encoding="utf-8")
        else:
            from tkinter import messagebox

            messagebox.showerror("ParrotIA could not start", detail)
        return 1
    return 0


if __name__ == "__main__":
    import multiprocessing

    _ensure_console_streams()
    multiprocessing.freeze_support()
    raise SystemExit(main())
