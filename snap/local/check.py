"""Installed-Snap diagnostics; no model downloads unless --model is given."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import time
from unittest.mock import patch
import io
import json
import os
import shutil
import wave
from pathlib import Path


def desktop_identity(app) -> dict:
    from configparser import ConfigParser

    desktop = ConfigParser(interpolation=None)
    desktop.read(Path(os.environ["SNAP"]) / "meta/gui/parrotia.desktop")
    expected = desktop["Desktop Entry"]["StartupWMClass"]
    actual = app.winfo_class()
    if actual != expected:
        raise RuntimeError(f"GNOME desktop identity mismatch: {actual} != {expected}")
    return {"wm_class": actual, "startup_wm_class": expected}


def exercise_desktop(mode_file: Path) -> dict:
    """Use an isolated test portal; never change the host's appearance settings."""
    import customtkinter as ctk
    from PIL import ImageGrab
    from parrotia.app import TranscriberApp, WINDOW_BG

    app = TranscriberApp()
    result = {"identity": desktop_identity(app), "fonts": font_rendering(app)}
    try:
        for value, expected, background in (
            (1, "Dark", WINDOW_BG[1]),
            (2, "Light", WINDOW_BG[0]),
            (1, "Dark", WINDOW_BG[1]),
        ):
            mode_file.write_text(str(value))
            deadline = time.monotonic() + 12
            while ctk.get_appearance_mode() != expected and time.monotonic() < deadline:
                app.update()
                time.sleep(0.02)
            app.update()
            assert ctk.get_appearance_mode() == expected, ctk.get_appearance_mode()
            actual = app.tk.call(app._w, "cget", "-background")
            assert app.winfo_rgb(actual) == app.winfo_rgb(background), actual
            x, y = app.winfo_rootx(), app.winfo_rooty()
            ImageGrab.grab(
                bbox=(x, y, x + app.winfo_width(), y + app.winfo_height())
            ).save(
                Path(os.environ["SNAP_USER_COMMON"])
                / f"qa-desktop-{expected.lower()}.png"
            )
        result["appearance_transitions"] = ["Dark", "Light", "Dark"]
        return result
    finally:
        app.destroy()


def font_rendering(app) -> dict:
    """Require real text/shape fonts and visible glyphs, not just Tk startup."""
    import tkinter as tk
    from tkinter import font
    from PIL import ImageGrab

    samples = {
        "Roboto": "ParrotIA Aa 0123",
        "DejaVu Sans": "Readable text 0123",
        "CustomTkinter_shapes_font": "A",
    }
    available = set(font.families(app))
    missing = set(samples) - available
    if missing:
        raise RuntimeError(f"Required bundled fonts are unavailable: {sorted(missing)}")
    probe = tk.Toplevel(app)
    probe.geometry("+0+0")
    probe.configure(background="white")
    labels = []
    fonts = []  # Keep Tk font objects alive until after the capture.
    try:
        for family, text in samples.items():
            selected = font.Font(root=app, family=family, size=-32)
            if selected.actual("family") != family:
                raise RuntimeError(f"Font unexpectedly substituted: {family}")
            fonts.append(selected)
            label = tk.Label(
                probe,
                text=text,
                font=selected,
                foreground="black",
                background="white",
                padx=10,
                pady=10,
            )
            label.pack()
            labels.append((family, label))
        probe.lift()
        app.update()
        result = {}
        for family, label in labels:
            x, y = label.winfo_rootx(), label.winfo_rooty()
            pixels = ImageGrab.grab(
                bbox=(x, y, x + label.winfo_width(), y + label.winfo_height())
            ).convert("RGB")
            ink = sum(pixels.convert("L").histogram()[:128])
            if ink < 30:
                raise RuntimeError(
                    f"Font rendered no readable glyphs: {family} ({ink})"
                )
            result[family] = {"ink_pixels": ink}
        x, y = probe.winfo_rootx(), probe.winfo_rooty()
        ImageGrab.grab(
            bbox=(x, y, x + probe.winfo_width(), y + probe.winfo_height())
        ).save(Path(os.environ["SNAP_USER_COMMON"]) / "qa-fonts.png")
        return result
    finally:
        probe.destroy()


def exercise_gui(audio: Path) -> dict:
    """Drive real GUI controls and worker threads under the test display."""
    from parrotia.app import TranscriberApp
    from parrotia.transcriber import LANGUAGES

    output = audio.parent / "GUI outputs"
    output.mkdir(exist_ok=True)
    dialogs = []
    app = TranscriberApp()
    identity = desktop_identity(app)
    fonts = font_rendering(app)
    app.model_var.set("tiny")
    app.language_var.set(next(k for k, v in LANGUAGES.items() if v == "en"))
    app.device_var.set("cpu")
    app.compute_var.set("int8")
    app.outdir_entry.insert(0, str(output))
    for var in app.format_vars.values():
        var.set(True)

    def wait() -> None:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            app.update()
            if (
                app.transcribe_btn.cget("state") == "normal"
                and not app._worker.is_alive()
            ):
                return
            time.sleep(0.02)
        raise TimeoutError("GUI transcription/cancellation did not finish")

    with (
        patch(
            "parrotia.app.messagebox.showinfo",
            side_effect=lambda *a, **k: dialogs.append(a),
        ),
        patch(
            "parrotia.app.messagebox.showerror",
            side_effect=lambda *a, **k: dialogs.append(a),
        ),
    ):
        try:
            app.file_entry.insert(0, str(audio))
            app.update()
            app.transcribe_btn.invoke()
            wait()
            assert "Done." in app.status.cget("text"), app.status.cget("text")
            transcript = app.preview.get("1.0", "end").strip()
            assert transcript and "test" in transcript.lower(), transcript
            for suffix in ["txt", "md", "srt", "vtt", "json"]:
                assert (output / (audio.stem + "." + suffix)).stat().st_size > 0
            from PIL import ImageGrab

            app.update()
            x, y = app.winfo_rootx(), app.winfo_rooty()
            screenshot = Path(os.environ["SNAP_USER_COMMON"]) / "qa-gui.png"
            ImageGrab.grab(
                bbox=(x, y, x + app.winfo_width(), y + app.winfo_height())
            ).save(screenshot)
            # A damaged recording must not abort the valid file in a batch.
            batch = audio.parent / "GUI batch"
            batch.mkdir(exist_ok=True)
            shutil.copy2(audio, batch / "01-valid.wav")
            (batch / "02-damaged.wav").write_bytes(b"not an audio file")
            app.file_entry.delete(0, "end")
            app.file_entry.insert(0, str(batch))
            app.transcribe_btn.invoke()
            wait()
            assert "1 failed" in app.status.cget("text"), app.status.cget("text")
            assert (output / "01-valid.txt").stat().st_size > 0
            # Cancel an actual queued job through the same button users press.
            app.transcribe_btn.invoke()
            app.after(20, app.cancel_btn.invoke)
            wait()
            assert "cancel" in app.status.cget("text").lower(), app.status.cget("text")
            return {
                "fonts": fonts,
                "desktop": identity,
                "transcription": transcript,
                "formats": 5,
                "cancellation": "ok",
                "batch_error_recovery": "ok",
                "screenshot": str(screenshot),
                "completion_dialogs": len(dialogs),
            }
        finally:
            app.destroy()


def provenance() -> dict:
    import av
    import numpy

    root = Path(os.environ["SNAP"])
    docs = root / "share/doc/parrotia/native"
    lock = json.loads((docs / "native-sources.json").read_text())
    for source in lock["sources"]:
        path = docs / "sources" / source["name"]
        with path.open("rb") as stream:
            assert (
                hashlib.file_digest(stream, "sha256").hexdigest() == source["sha256"]
            ), path
    lib = ctypes.CDLL(str(root / "usr/lib/libavutil.so.60"))
    lib.avutil_license.restype = ctypes.c_char_p
    lib.avutil_configuration.restype = ctypes.c_char_p
    license_text = lib.avutil_license().decode()
    flags = lib.avutil_configuration().decode()
    assert license_text == "LGPL version 2.1 or later", license_text
    assert "--enable-gpl" not in flags and "--enable-nonfree" not in flags, flags
    assert av.ffmpeg_version_info == lock["versions"]["ffmpeg"], av.ffmpeg_version_info
    site = Path(numpy.__file__).parent.parent
    for name in ["av", "numpy", "ctranslate2"]:
        assert not (site / (name + ".libs")).exists(), name
    return {
        "ffmpeg": av.ffmpeg_version_info,
        "ffmpeg_license": license_text,
        "source_archives_verified": len(lock["sources"]),
        "native_wheel_bundles": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gui", action="store_true", help="Also construct the GUI")
    parser.add_argument("--model", help="Download/load a model and transcribe silence")
    parser.add_argument(
        "--exercise-desktop", type=Path, help="Use the isolated QA portal"
    )
    parser.add_argument(
        "--exercise-gui",
        type=Path,
        help="Test real GUI transcription and cancellation on a speech fixture",
    )
    args = parser.parse_args()

    import ctranslate2
    from faster_whisper.audio import decode_audio
    from faster_whisper.vad import get_vad_model
    from huggingface_hub.constants import HF_HUB_CACHE

    from parrotia import __version__

    common = Path(os.environ["SNAP_USER_COMMON"])
    cache = Path(HF_HUB_CACHE)
    assert cache == common / "huggingface" / "hub", cache
    assert cache.is_dir(), cache
    audio = io.BytesIO()
    with wave.open(audio, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\0\0" * 16000)
    audio.seek(0)
    samples = decode_audio(audio)
    assert len(samples) == 16000, len(samples)
    get_vad_model()
    report = {
        "version": __version__,
        "samples": len(samples),
        "cpu_compute_types": sorted(ctranslate2.get_supported_compute_types("cpu")),
        "model_cache": str(cache),
    }
    report["native_provenance"] = provenance()
    if args.exercise_desktop:
        report["desktop"] = exercise_desktop(args.exercise_desktop)
    if args.exercise_gui:
        report["gui_workflow"] = exercise_gui(args.exercise_gui)
    if args.gui:
        from parrotia.app import TranscriberApp

        app = TranscriberApp()
        report["desktop"] = desktop_identity(app)
        report["fonts"] = font_rendering(app)
        app.withdraw()
        app.update()
        app.destroy()
        report["gui"] = "ok"
    if args.model:
        from faster_whisper import WhisperModel

        model = WhisperModel(args.model, device="cpu", compute_type="int8")
        audio.seek(0)
        segments, _ = model.transcribe(audio, vad_filter=False)
        report["transcribed_segments"] = len(list(segments))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
