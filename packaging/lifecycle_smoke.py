"""Real GUI/model lifecycle checks, run in a fresh frozen process per scenario."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import wave
from pathlib import Path


def run(report: Path, scenario: str) -> None:
    from parrotia.app import TranscriberApp

    model = os.environ["PARROTIA_SMOKE_MODEL_NAME"]
    app = TranscriberApp()
    app.withdraw()
    app.model_var.set(model)
    transcribe = app._transcriber.transcribe

    def full_decode(path, **settings):
        return transcribe(path, vad_filter=False, **settings)

    app._transcriber.transcribe = full_decode
    # Suppress completion dialogs in this controlled, noninteractive check.
    original_handle = app._handle_event
    completed = []
    closing_processes = []
    gaps = []
    errors = []
    last_tick = time.monotonic()
    started = time.monotonic()

    def close():
        if app._closing:
            return
        closing_processes.append(app._transcriber._process)
        if scenario == "active" and sys.platform == "darwin":
            app.tk.call("::tk::mac::Quit")
        else:
            app._on_close()

    def handle(event):
        if event[0] == "batch_done":
            completed.append(event)
            close()
        elif event[0] == "error":
            errors.append(str(event[1]))
            close()
        else:
            original_handle(event)
            # Close after loading has allocated a model, during analysis/decode.
            if scenario == "active" and event[0] == "progress" and event[1] >= 0.1:
                close()

    def tick():
        nonlocal last_tick
        now = time.monotonic()
        gaps.append(now - last_tick)
        last_tick = now
        if now - started > 45:
            errors.append("GUI lifecycle timed out")
            close()
        if not app._closing:
            app.after(20, tick)

    app._handle_event = handle
    app.after(20, tick)
    with tempfile.TemporaryDirectory(prefix="parrotia-lifecycle-") as tmp:
        audio = Path(tmp) / "silence.wav"
        with wave.open(str(audio), "wb") as wav:
            wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            wav.writeframes(b"\0\0" * 16000 * 5)
        app.file_entry.insert(0, str(audio))
        app.after(100, app._start_transcription)
        app.mainloop()
    elapsed = time.monotonic() - started
    if errors:
        raise RuntimeError("; ".join(errors))
    if scenario == "complete":
        if not completed or completed[0][2]:
            raise RuntimeError(
                f"Transcription did not complete successfully: {completed}"
            )
    if not closing_processes or any(
        p is None or p.is_alive() for p in closing_processes
    ):
        raise RuntimeError("Inference worker survived GUI shutdown")
    if scenario == "complete" and any(p.exitcode != 0 for p in closing_processes):
        raise RuntimeError("Native cleanup did not exit cleanly")
    if max(gaps, default=0) > 1.0:
        raise RuntimeError(f"GUI heartbeat stalled for {max(gaps):.2f}s")
    report.write_text(
        json.dumps(
            {
                "scenario": scenario,
                "elapsed": elapsed,
                "max_gui_gap": max(gaps),
                "worker_exit_codes": [p.exitcode for p in closing_processes],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
