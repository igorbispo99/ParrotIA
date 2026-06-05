"""Audio Transcriber — a local, free, GUI Whisper transcription tool.

Run with:  python app.py
"""

from __future__ import annotations

import queue
import threading
import traceback
from pathlib import Path
from typing import Optional

import customtkinter as ctk
from tkinter import filedialog, messagebox

import formats
from transcriber import (
    AVAILABLE_MODELS,
    COMPUTE_TYPES,
    DEFAULT_MODEL,
    DEVICES,
    LANGUAGES,
    SUPPORTED_EXTENSIONS,
    TranscriptionCancelled,
    TranscriptionResult,
    Transcriber,
)

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

_AUDIO_FILETYPES = [
    ("Audio / Video", " ".join(f"*{ext}" for ext in SUPPORTED_EXTENSIONS)),
    ("All files", "*.*"),
]


class TranscriberApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.title("Audio Transcriber")
        self.geometry("820x760")
        self.minsize(720, 640)

        self._transcriber = Transcriber()
        self._worker: Optional[threading.Thread] = None
        self._cancel_event = threading.Event()
        self._events: "queue.Queue[tuple]" = queue.Queue()
        self._result: Optional[TranscriptionResult] = None
        self._input_path: Optional[Path] = None

        self._build_ui()
        self.after(100, self._drain_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ----------------------------------------------------------------- UI ---
    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)
        pad = {"padx": 16, "pady": (0, 12)}

        header = ctk.CTkLabel(
            self, text="🎙  Audio Transcriber",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        header.grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))

        subtitle = ctk.CTkLabel(
            self,
            text="Fast, fully local transcription powered by Whisper. "
                 "No internet or API keys required.",
            text_color=("gray40", "gray60"),
        )
        subtitle.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 12))

        # --- File selection -------------------------------------------------
        file_frame = ctk.CTkFrame(self)
        file_frame.grid(row=2, column=0, sticky="ew", **pad)
        file_frame.grid_columnconfigure(0, weight=1)

        self.file_entry = ctk.CTkEntry(
            file_frame, placeholder_text="Select an audio or video file…"
        )
        self.file_entry.grid(row=0, column=0, sticky="ew", padx=(12, 8), pady=12)
        ctk.CTkButton(
            file_frame, text="Browse…", width=110, command=self._browse_input
        ).grid(row=0, column=1, padx=(0, 12), pady=12)

        # --- Options --------------------------------------------------------
        options = ctk.CTkFrame(self)
        options.grid(row=3, column=0, sticky="ew", **pad)
        for col in (1, 3):
            options.grid_columnconfigure(col, weight=1)

        self.model_var = ctk.StringVar(value=DEFAULT_MODEL)
        self.language_var = ctk.StringVar(value="Auto detect")
        self.device_var = ctk.StringVar(value=DEVICES[0])
        self.compute_var = ctk.StringVar(value=COMPUTE_TYPES[0])

        self._add_option(options, 0, 0, "Model", AVAILABLE_MODELS, self.model_var)
        self._add_option(options, 0, 2, "Language",
                         list(LANGUAGES.keys()), self.language_var)
        self._add_option(options, 1, 0, "Device", DEVICES, self.device_var)
        self._add_option(options, 1, 2, "Compute", COMPUTE_TYPES, self.compute_var)

        # --- Output formats + folder ---------------------------------------
        output = ctk.CTkFrame(self)
        output.grid(row=4, column=0, sticky="ew", **pad)
        output.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(output, text="Save as", anchor="w").grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 4))

        formats_row = ctk.CTkFrame(output, fg_color="transparent")
        formats_row.grid(row=1, column=0, sticky="w", padx=8)
        self.format_vars: "dict[str, ctk.BooleanVar]" = {}
        defaults = {"txt", "md", "srt"}
        for i, fmt in enumerate(formats.WRITERS):
            var = ctk.BooleanVar(value=fmt in defaults)
            ctk.CTkCheckBox(
                formats_row, text=fmt.upper(), variable=var, width=70
            ).grid(row=0, column=i, padx=6, pady=4)
            self.format_vars[fmt] = var

        out_row = ctk.CTkFrame(output, fg_color="transparent")
        out_row.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 12))
        out_row.grid_columnconfigure(0, weight=1)
        self.outdir_entry = ctk.CTkEntry(
            out_row, placeholder_text="Output folder (defaults to source folder)"
        )
        self.outdir_entry.grid(row=0, column=0, sticky="ew", padx=(4, 8))
        ctk.CTkButton(
            out_row, text="Choose…", width=110, command=self._browse_outdir
        ).grid(row=0, column=1, padx=(0, 4))

        # --- Preview --------------------------------------------------------
        self.preview = ctk.CTkTextbox(self, wrap="word")
        self.preview.grid(row=5, column=0, sticky="nsew", padx=16, pady=(0, 12))
        self.preview.insert("1.0", "Transcript preview will appear here…")
        self.preview.configure(state="disabled")

        # --- Action bar -----------------------------------------------------
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=6, column=0, sticky="ew", padx=16, pady=(0, 8))
        bar.grid_columnconfigure(1, weight=1)

        self.transcribe_btn = ctk.CTkButton(
            bar, text="Transcribe", width=140, height=40,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._start_transcription,
        )
        self.transcribe_btn.grid(row=0, column=0, sticky="w")

        self.cancel_btn = ctk.CTkButton(
            bar, text="Cancel", width=100, height=40,
            fg_color="gray40", hover_color="gray30",
            command=self._cancel_transcription, state="disabled",
        )
        self.cancel_btn.grid(row=0, column=2, sticky="e")

        # --- Progress / status ---------------------------------------------
        self.progress = ctk.CTkProgressBar(self)
        self.progress.grid(row=7, column=0, sticky="ew", padx=16, pady=(0, 4))
        self.progress.set(0.0)

        self.status = ctk.CTkLabel(
            self, text="Ready.", anchor="w", text_color=("gray40", "gray60")
        )
        self.status.grid(row=8, column=0, sticky="ew", padx=16, pady=(0, 12))

    def _add_option(self, parent, row, col, label, values, variable) -> None:
        ctk.CTkLabel(parent, text=label, anchor="w").grid(
            row=row, column=col, sticky="w", padx=(12, 6), pady=10)
        ctk.CTkOptionMenu(parent, values=values, variable=variable).grid(
            row=row, column=col + 1, sticky="ew", padx=(0, 12), pady=10)

    # ------------------------------------------------------------ actions ---
    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Select audio or video", filetypes=_AUDIO_FILETYPES)
        if path:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, path)

    def _browse_outdir(self) -> None:
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            self.outdir_entry.delete(0, "end")
            self.outdir_entry.insert(0, path)

    def _start_transcription(self) -> None:
        if self._worker and self._worker.is_alive():
            return

        raw_path = self.file_entry.get().strip().strip('"')
        if not raw_path:
            messagebox.showwarning("No file", "Please choose an audio file first.")
            return
        path = Path(raw_path)
        if not path.is_file():
            messagebox.showerror("Not found", f"File does not exist:\n{raw_path}")
            return
        if not any(var.get() for var in self.format_vars.values()):
            messagebox.showwarning(
                "No format", "Select at least one output format.")
            return

        self._input_path = path
        self._cancel_event.clear()
        self._set_running(True)
        self._set_preview("")
        self._set_status("Starting…")
        self.progress.set(0.0)

        params = dict(
            model=self.model_var.get(),
            language=LANGUAGES[self.language_var.get()],
            device=self.device_var.get(),
            compute_type=self.compute_var.get(),
        )
        self._worker = threading.Thread(
            target=self._run_worker, args=(str(path), params), daemon=True)
        self._worker.start()

    def _cancel_transcription(self) -> None:
        self._cancel_event.set()
        self._set_status("Cancelling…")

    # ------------------------------------------------------------- worker ---
    def _run_worker(self, path: str, params: dict) -> None:
        try:
            result = self._transcriber.transcribe(
                path,
                progress_callback=lambda frac, msg: self._events.put(
                    ("progress", frac, msg)),
                cancel_event=self._cancel_event,
                **params,
            )
            self._events.put(("done", result))
        except TranscriptionCancelled:
            self._events.put(("cancelled",))
        except Exception as exc:  # surfaced to the user in the GUI thread
            self._events.put(("error", exc, traceback.format_exc()))

    def _drain_events(self) -> None:
        try:
            while True:
                event = self._events.get_nowait()
                self._handle_event(event)
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _handle_event(self, event: tuple) -> None:
        kind = event[0]
        if kind == "progress":
            _, fraction, message = event
            self.progress.set(fraction)
            self._set_status(message)
        elif kind == "done":
            self._on_done(event[1])
        elif kind == "cancelled":
            self._set_running(False)
            self.progress.set(0.0)
            self._set_status("Cancelled.")
        elif kind == "error":
            self._set_running(False)
            self.progress.set(0.0)
            self._set_status("Error.")
            messagebox.showerror("Transcription failed", str(event[1]))

    def _on_done(self, result: TranscriptionResult) -> None:
        self._result = result
        self.progress.set(1.0)
        self._set_preview(formats.to_txt(result))
        try:
            written = self._write_outputs(result)
        except Exception as exc:
            self._set_running(False)
            messagebox.showerror("Could not save files", str(exc))
            return
        self._set_running(False)
        self._set_status(
            f"Done — {len(result.segments)} segments. Saved: "
            + ", ".join(p.name for p in written)
        )
        messagebox.showinfo(
            "Transcription complete",
            "Saved files:\n" + "\n".join(str(p) for p in written),
        )

    def _write_outputs(self, result: TranscriptionResult) -> list:
        assert self._input_path is not None
        outdir_raw = self.outdir_entry.get().strip().strip('"')
        outdir = Path(outdir_raw) if outdir_raw else self._input_path.parent
        outdir.mkdir(parents=True, exist_ok=True)
        stem = self._input_path.stem

        written = []
        for fmt, var in self.format_vars.items():
            if not var.get():
                continue
            extension, writer = formats.WRITERS[fmt]
            target = outdir / f"{stem}{extension}"
            target.write_text(writer(result), encoding="utf-8")
            written.append(target)
        return written

    # -------------------------------------------------------------- state ---
    def _set_running(self, running: bool) -> None:
        self.transcribe_btn.configure(state="disabled" if running else "normal")
        self.cancel_btn.configure(state="normal" if running else "disabled")

    def _set_status(self, message: str) -> None:
        self.status.configure(text=message)

    def _set_preview(self, text: str) -> None:
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def _on_close(self) -> None:
        self._cancel_event.set()
        self.destroy()


def main() -> None:
    app = TranscriberApp()
    app.mainloop()


if __name__ == "__main__":
    main()
