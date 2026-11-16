"""Standalone desktop executable: the GUI or Windows Explorer's queue."""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path


def _smoke_test(report: Path, packaged: bool) -> None:
    """Exercise native dependencies and Tk without downloading a model."""
    import io
    import tkinter
    import wave

    import av
    import ctranslate2
    import customtkinter
    import tokenizers
    from faster_whisper.audio import decode_audio
    from faster_whisper.vad import get_vad_model

    from parrotia import __version__
    from parrotia.app import TranscriberApp

    stream = io.BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * 1600)
    stream.seek(0)
    samples = decode_audio(stream)
    get_vad_model()  # Loads the bundled Silero ONNX model and native runtime.
    app = TranscriberApp()
    app.withdraw()
    app.update()
    app.destroy()
    hf_home = os.environ.get("HF_HOME")
    if packaged and hf_home:
        # Lets test-msix.ps1 confirm the cache lands in package storage,
        # which Windows removes on uninstall.
        Path(hf_home).mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(
            {
                "version": __version__,
                "packaged": packaged,
                "hf_home": hf_home,
                "samples": len(samples),
                "av": av.__version__,
                "ctranslate2": ctranslate2.__version__,
                "customtkinter": customtkinter.__version__,
                "tokenizers": tokenizers.__version__,
                "tk": tkinter.TkVersion,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> int:
    # Windowed executables have no console streams. Native dependency startup
    # warnings still write to them, so provide valid sinks before any imports.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115 -- process lifetime
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115 -- process lifetime
    try:
        # The Store (MSIX) build needs its own defaults before any model library loads.
        from parrotia._msix import configure_packaged_environment

        packaged = configure_packaged_environment()
        # Pin taskbar identity to our executable and icon, rather than python.exe.
        # Packaged apps must keep the identity Windows assigns to the package.
        if sys.platform == "win32" and not packaged:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "ParrotIA.Desktop"
            )
        if len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
            _smoke_test(Path(sys.argv[2]), packaged)
        elif len(sys.argv) > 1 and sys.argv[1] == "--shell":
            from parrotia.explorer import main as explorer_main

            return explorer_main(sys.argv[2:])
        else:
            from parrotia.app import main as gui_main

            # "Open with" passes the chosen media file(s) as arguments.
            gui_main(sys.argv[1:])
    except Exception:  # noqa: BLE001 -- surface startup errors from any dependency
        detail = traceback.format_exc()
        print(detail, file=sys.stderr)
        if len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
            # Never show a dialog in unattended checks; the exit code reports it.
            try:
                Path(sys.argv[2]).write_text(detail, encoding="utf-8")
            except OSError:
                pass
        else:
            from tkinter import messagebox

            messagebox.showerror("ParrotIA could not start", detail)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
