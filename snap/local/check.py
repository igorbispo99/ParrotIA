"""Installed-Snap diagnostics; no model downloads unless --model is given."""

from __future__ import annotations

import argparse
import io
import json
import os
import wave
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gui", action="store_true", help="Also construct the GUI")
    parser.add_argument("--model", help="Download/load a model and transcribe silence")
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
    if args.gui:
        from parrotia.app import TranscriberApp

        app = TranscriberApp()
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
