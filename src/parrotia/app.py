"""Audio Transcriber — a local, free, GUI Whisper transcription tool.

Run with:  parrotia-gui   (or:  python -m parrotia.app)
"""

from __future__ import annotations

import queue
import threading
import traceback
from pathlib import Path
from typing import Optional

import customtkinter as ctk
from tkinter import filedialog, messagebox

from . import formats
from .transcriber import (
    AVAILABLE_MODELS,
    COMPUTE_TYPES,
    DEFAULT_MODEL,
    DEVICES,
    LANGUAGES,
    MODEL_SIZES,
    SUPPORTED_EXTENSIONS,
    TranscriptionCancelled,
    TranscriptionResult,
    Transcriber,
)

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# --- Brand palette, drawn from banner.png ----------------------------------
# A tropical macaw over a teal sea: parrot-green body, golden belly, sky-blue
# wings and a coral face. These few colours give the whole UI its personality.
TEAL_DARK = "#0E7C7B"  # the sea behind the parrot
GREEN = "#1FAE6B"  # parrot body  -> primary "go" actions
GREEN_HI = "#17935A"
GOLD = "#F4B740"  # golden belly -> the "IA" in the wordmark, highlights
BLUE = "#2D7DD2"  # wing blue    -> secondary buttons / inputs
CORAL = "#EF5B5B"  # parrot face  -> cancel / destructive
CORAL_HI = "#D94848"

# Tuple colours are (light-mode, dark-mode) so the theme adapts to the system.
WINDOW_BG = ("#E8F6F4", "#0B2B2C")
CARD_BG = ("#FFFFFF", "#10393A")
CARD_SOFT = ("#F3FBFA", "#0E3233")
INK = ("#0E3233", "#EAF6F4")
MUTED = ("#5A7572", "#8FB7B5")

# Banner-style feature badges: (label, colour).
_BADGES = [
    ("🔒 100% Offline", TEAL_DARK),
    ("🚫 No Internet", BLUE),
    ("⚡ Fast & Easy", GOLD),
    ("🦜 Powered by Whisper", GREEN),
]

_AUDIO_FILETYPES = [
    ("Audio / Video", " ".join(f"*{ext}" for ext in SUPPORTED_EXTENSIONS)),
    ("All files", "*.*"),
]


class TranscriberApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.title("ParrotIA — Local Audio & Video Transcriber")
        self.geometry("860x820")
        self.minsize(740, 680)
        self.configure(fg_color=WINDOW_BG)

        self._transcriber = Transcriber()
        self._worker: Optional[threading.Thread] = None
        self._cancel_event = threading.Event()
        self._events: "queue.Queue[tuple]" = queue.Queue()
        self._result: Optional[TranscriptionResult] = None
        self._total_jobs = 0
        self._downloading = False

        self._build_ui()
        self.after(100, self._drain_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ----------------------------------------------------------------- UI ---
    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        self._build_hero()

        # --- Input selection (a single file, or a whole folder) -------------
        file_frame = self._card(row=1)
        file_frame.grid_columnconfigure(0, weight=1)
        self._heading(file_frame, "📁  Choose audio or video", row=0)

        self.file_entry = ctk.CTkEntry(
            file_frame,
            height=38,
            border_color=BLUE,
            placeholder_text="Pick a file — or a whole folder to batch them all…",
        )
        self.file_entry.grid(row=1, column=0, sticky="ew", padx=(14, 8), pady=(0, 14))
        ctk.CTkButton(
            file_frame,
            text="File…",
            width=84,
            height=38,
            fg_color=BLUE,
            hover_color="#246CB8",
            command=self._browse_input,
        ).grid(row=1, column=1, padx=(0, 6), pady=(0, 14))
        ctk.CTkButton(
            file_frame,
            text="Folder…",
            width=92,
            height=38,
            fg_color=BLUE,
            hover_color="#246CB8",
            command=self._browse_folder,
        ).grid(row=1, column=2, padx=(0, 14), pady=(0, 14))

        # --- Options --------------------------------------------------------
        options = self._card(row=2)
        for col in (1, 3):
            options.grid_columnconfigure(col, weight=1)
        self._heading(options, "⚙️  Options", row=0, columnspan=4)

        self.model_var = ctk.StringVar(value=DEFAULT_MODEL)
        self.language_var = ctk.StringVar(value="Auto detect")
        self.device_var = ctk.StringVar(value=DEVICES[0])
        self.compute_var = ctk.StringVar(value=COMPUTE_TYPES[0])

        self._add_option(options, 1, 0, "Model", AVAILABLE_MODELS, self.model_var)
        self._add_option(
            options, 1, 2, "Language", list(LANGUAGES.keys()), self.language_var
        )
        self._add_option(options, 2, 0, "Device", DEVICES, self.device_var)
        self._add_option(options, 2, 2, "Compute", COMPUTE_TYPES, self.compute_var)

        # --- Output formats + folder ---------------------------------------
        output = self._card(row=3)
        output.grid_columnconfigure(0, weight=1)
        self._heading(output, "💾  Save as", row=0)

        formats_row = ctk.CTkFrame(output, fg_color="transparent")
        formats_row.grid(row=1, column=0, sticky="w", padx=8)
        self.format_vars: "dict[str, ctk.BooleanVar]" = {}
        defaults = {"txt", "md", "srt"}
        for i, fmt in enumerate(formats.WRITERS):
            var = ctk.BooleanVar(value=fmt in defaults)
            ctk.CTkCheckBox(
                formats_row,
                text=fmt.upper(),
                variable=var,
                width=70,
                fg_color=GREEN,
                hover_color=GREEN_HI,
            ).grid(row=0, column=i, padx=6, pady=4)
            self.format_vars[fmt] = var

        out_row = ctk.CTkFrame(output, fg_color="transparent")
        out_row.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 12))
        out_row.grid_columnconfigure(0, weight=1)
        self.outdir_entry = ctk.CTkEntry(
            out_row,
            height=38,
            border_color=BLUE,
            placeholder_text="Output folder (defaults to source folder)",
        )
        self.outdir_entry.grid(row=0, column=0, sticky="ew", padx=(4, 8))
        ctk.CTkButton(
            out_row,
            text="Choose…",
            width=110,
            height=38,
            fg_color=BLUE,
            hover_color="#246CB8",
            command=self._browse_outdir,
        ).grid(row=0, column=1, padx=(0, 4))

        # --- Preview --------------------------------------------------------
        preview_card = self._card(row=4, weight_row=1)
        preview_card.grid_columnconfigure(0, weight=1)
        preview_card.grid_rowconfigure(1, weight=1)
        self._heading(preview_card, "📝  Transcript", row=0)
        self.preview = ctk.CTkTextbox(
            preview_card,
            wrap="word",
            fg_color=CARD_SOFT,
            border_width=0,
        )
        self.preview.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.preview.insert("1.0", "🦜  Your transcript will land right here…")
        self.preview.configure(state="disabled")

        # --- Action bar -----------------------------------------------------
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=5, column=0, sticky="ew", padx=16, pady=(0, 8))
        bar.grid_columnconfigure(1, weight=1)

        self.transcribe_btn = ctk.CTkButton(
            bar,
            text="🦜  Transcribe",
            width=170,
            height=44,
            corner_radius=22,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=GREEN,
            hover_color=GREEN_HI,
            command=self._start_transcription,
        )
        self.transcribe_btn.grid(row=0, column=0, sticky="w")

        self.cancel_btn = ctk.CTkButton(
            bar,
            text="Cancel",
            width=110,
            height=44,
            corner_radius=22,
            fg_color=CORAL,
            hover_color=CORAL_HI,
            command=self._cancel_transcription,
            state="disabled",
        )
        self.cancel_btn.grid(row=0, column=2, sticky="e")

        # --- Progress / status ---------------------------------------------
        self.progress = ctk.CTkProgressBar(self, progress_color=GREEN, height=10)
        self.progress.grid(row=6, column=0, sticky="ew", padx=16, pady=(0, 4))
        self.progress.set(0.0)

        self.status = ctk.CTkLabel(
            self, text="Ready when you are.", anchor="w", text_color=MUTED
        )
        self.status.grid(row=7, column=0, sticky="ew", padx=16, pady=(0, 12))

    # --- Reusable visual building blocks (parrot-themed) --------------------
    def _build_hero(self) -> None:
        """A branded banner-style header: parrot logo, wordmark and badges."""
        hero = ctk.CTkFrame(self, fg_color=TEAL_DARK, corner_radius=16)
        hero.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 12))
        hero.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hero, text="🦜", font=ctk.CTkFont(size=52)).grid(
            row=0, column=0, rowspan=2, padx=(20, 10), pady=(16, 14)
        )

        wordmark = ctk.CTkFrame(hero, fg_color="transparent")
        wordmark.grid(row=0, column=1, sticky="w", padx=(0, 16), pady=(18, 0))
        ctk.CTkLabel(
            wordmark,
            text="Parrot",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=30, weight="bold"),
        ).grid(row=0, column=0)
        ctk.CTkLabel(
            wordmark,
            text="IA",
            text_color=GOLD,
            font=ctk.CTkFont(size=30, weight="bold"),
        ).grid(row=0, column=1)

        ctk.CTkLabel(
            hero,
            text="Local Audio & Video Transcriber",
            text_color="#C9E9E6",
            font=ctk.CTkFont(size=13),
        ).grid(row=1, column=1, sticky="w", padx=(0, 16), pady=(0, 6))

        badges = ctk.CTkFrame(hero, fg_color="transparent")
        badges.grid(row=2, column=0, columnspan=2, sticky="w", padx=18, pady=(2, 16))
        for i, (text, color) in enumerate(_BADGES):
            ctk.CTkLabel(
                badges,
                text=f"  {text}  ",
                height=26,
                corner_radius=13,
                fg_color=color,
                text_color="#FFFFFF",
                font=ctk.CTkFont(size=11, weight="bold"),
            ).grid(row=0, column=i, padx=(0, 8))

    def _card(self, row: int, weight_row: bool = False) -> ctk.CTkFrame:
        card = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=14)
        sticky = "nsew" if weight_row else "ew"
        card.grid(row=row, column=0, sticky=sticky, padx=16, pady=(0, 12))
        return card

    def _heading(self, parent, text: str, row: int, columnspan: int = 1) -> None:
        ctk.CTkLabel(
            parent,
            text=text,
            anchor="w",
            text_color=INK,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(
            row=row, column=0, columnspan=columnspan, sticky="w", padx=14, pady=(12, 8)
        )

    def _add_option(self, parent, row, col, label, values, variable) -> None:
        ctk.CTkLabel(parent, text=label, anchor="w", text_color=MUTED).grid(
            row=row, column=col, sticky="w", padx=(14, 6), pady=10
        )
        ctk.CTkOptionMenu(
            parent,
            values=values,
            variable=variable,
            height=34,
            fg_color=TEAL_DARK,
            button_color=GREEN,
            button_hover_color=GREEN_HI,
        ).grid(row=row, column=col + 1, sticky="ew", padx=(0, 14), pady=10)

    # ------------------------------------------------------------ actions ---
    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Select audio or video", filetypes=_AUDIO_FILETYPES
        )
        if path:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, path)

    def _browse_folder(self) -> None:
        path = filedialog.askdirectory(title="Select a folder of audio/video files")
        if path:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, path)

    @staticmethod
    def _collect_audio_files(folder: Path) -> "list[Path]":
        """Supported audio/video files directly inside ``folder``, sorted."""
        exts = {ext.lower() for ext in SUPPORTED_EXTENSIONS}
        return sorted(
            p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in exts
        )

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
            messagebox.showwarning(
                "No input", "Please choose an audio file or a folder first."
            )
            return
        path = Path(raw_path)

        # Resolve the input to a list of files to transcribe: a single file, or
        # every supported audio/video file directly inside a chosen folder.
        if path.is_dir():
            jobs = self._collect_audio_files(path)
            if not jobs:
                messagebox.showwarning(
                    "No audio files",
                    f"No supported audio/video files were found in:\n{raw_path}",
                )
                return
        elif path.is_file():
            jobs = [path]
        else:
            messagebox.showerror("Not found", f"No such file or folder:\n{raw_path}")
            return

        selected_formats = [f for f, v in self.format_vars.items() if v.get()]
        if not selected_formats:
            messagebox.showwarning("No format", "Select at least one output format.")
            return
        outdir_raw = self.outdir_entry.get().strip().strip('"')

        self._total_jobs = len(jobs)
        self._cancel_event.clear()
        self._set_running(True)
        self._set_preview("")

        params = dict(
            model=self.model_var.get(),
            language=LANGUAGES[self.language_var.get()],
            device=self.device_var.get(),
            compute_type=self.compute_var.get(),
        )

        # Check if model needs downloading (first-time setup)
        needs_download = not Transcriber.is_model_cached(params["model"])
        if needs_download:
            self._downloading = True
            size = MODEL_SIZES.get(params["model"], "")
            hint = f" ({size})" if size else ""
            self._set_status(
                f"📥 Downloading model '{params['model']}'{hint}"
                " — first time setup, please wait…"
            )
            self.progress.configure(mode="indeterminate")
            self.progress.start()
        else:
            self._downloading = False
            self._set_status(
                f"Starting… ({self._total_jobs} files)"
                if self._total_jobs > 1
                else "Starting…"
            )
            self.progress.set(0.0)
        self._worker = threading.Thread(
            target=self._run_worker,
            args=(jobs, params, selected_formats, outdir_raw),
            daemon=True,
        )
        self._worker.start()

    def _cancel_transcription(self) -> None:
        self._cancel_event.set()
        self._set_status("Cancelling…")

    # ------------------------------------------------------------- worker ---
    def _run_worker(
        self,
        jobs: "list[Path]",
        params: dict,
        selected_formats: "list[str]",
        outdir_raw: str,
    ) -> None:
        """Transcribe every file in ``jobs`` in turn, on this daemon thread.

        Progress is reported as an overall fraction across all files; a
        per-file failure is collected and the batch continues. Output files are
        written here (pure disk I/O on a snapshot of the settings, so no Tk
        widgets are touched off the main thread).
        """
        total = len(jobs)
        written_all: "list[Path]" = []
        errors: "list[tuple[Path, str]]" = []
        try:
            for index, source in enumerate(jobs):
                if self._cancel_event.is_set():
                    self._events.put(("cancelled",))
                    return

                base, span = index / total, 1 / total

                def report(frac: float, msg: str, _i=index, _name=source.name) -> None:
                    overall = base + span * frac
                    prefix = f"[{_i + 1}/{total}] {_name} — " if total > 1 else ""
                    self._events.put(("progress", overall, prefix + msg))

                try:
                    result = self._transcriber.transcribe(
                        str(source),
                        progress_callback=report,
                        cancel_event=self._cancel_event,
                        **params,
                    )
                    written = self._write_result(
                        result, source, selected_formats, outdir_raw
                    )
                except TranscriptionCancelled:
                    self._events.put(("cancelled",))
                    return
                except Exception as exc:  # don't let one bad file abort the batch
                    errors.append((source, str(exc)))
                    continue

                written_all.extend(written)
                self._events.put(("file_done", source, result, written))

            self._events.put(("batch_done", written_all, errors, total))
        except Exception as exc:  # truly unexpected — surface in the GUI thread
            self._events.put(("error", exc, traceback.format_exc()))

    @staticmethod
    def _write_result(
        result: TranscriptionResult,
        source: Path,
        selected_formats: "list[str]",
        outdir_raw: str,
    ) -> "list[Path]":
        outdir = Path(outdir_raw) if outdir_raw else source.parent
        outdir.mkdir(parents=True, exist_ok=True)
        stem = source.stem
        written = []
        for fmt in selected_formats:
            extension, writer = formats.WRITERS[fmt]
            target = outdir / f"{stem}{extension}"
            target.write_text(writer(result), encoding="utf-8")
            written.append(target)
        return written

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
            if self._downloading and fraction > 0:
                # Model download/load complete — switch to normal progress.
                self._downloading = False
                self.progress.stop()
                self.progress.configure(mode="determinate")
            if not self._downloading:
                self.progress.set(fraction)
            self._set_status(message)
        elif kind == "file_done":
            self._on_file_done(event[1], event[2])
        elif kind == "batch_done":
            self._on_batch_done(event[1], event[2], event[3])
        elif kind == "cancelled":
            if self._downloading:
                self._downloading = False
                self.progress.stop()
                self.progress.configure(mode="determinate")
            self._set_running(False)
            self.progress.set(0.0)
            self._set_status("Cancelled.")
        elif kind == "error":
            if self._downloading:
                self._downloading = False
                self.progress.stop()
                self.progress.configure(mode="determinate")
            self._set_running(False)
            self.progress.set(0.0)
            self._set_status("Error.")
            messagebox.showerror("Transcription failed", str(event[1]))

    def _on_file_done(self, source: Path, result: TranscriptionResult) -> None:
        # Show the just-finished transcript; in batch mode prefix a small header
        # so it's clear which file the preview belongs to.
        self._result = result
        text = formats.to_txt(result)
        if self._total_jobs > 1:
            text = f"▸ {source.name}\n\n{text}"
        self._set_preview(text)

    def _on_batch_done(self, written: "list[Path]", errors: list, total: int) -> None:
        self._set_running(False)
        self.progress.set(1.0)
        ok = total - len(errors)

        if total == 1 and not errors:
            self._set_status("Done. Saved: " + ", ".join(p.name for p in written))
            messagebox.showinfo(
                "Transcription complete",
                "Saved files:\n" + "\n".join(str(p) for p in written),
            )
            return

        self._set_status(
            f"Done — {ok}/{total} files transcribed"
            + (f", {len(errors)} failed." if errors else ", all saved.")
        )
        lines = [
            f"Transcribed {ok} of {total} file(s); saved {len(written)} output file(s)."
        ]
        if errors:
            lines.append("")
            lines.append("Failed:")
            lines.extend(f"  • {src.name}: {msg}" for src, msg in errors)
        messagebox.showinfo("Batch complete", "\n".join(lines))

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
