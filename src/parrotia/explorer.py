"""Windows Explorer's one-click transcription queue.

Explorer launches a legacy verb once per selected file. Requests are published
atomically and one process owns the queue, so a selection shares one model and
one progress window. No shell commands are constructed from filenames.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import threading
import time
import uuid
from pathlib import Path

from . import formats
from .transcriber import SUPPORTED_EXTENSIONS, Transcriber, TranscriptionCancelled


class _FileLock:
    """A Windows byte-range lock, automatically released if a process dies."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle = None

    def acquire(self, *, wait: bool = False) -> bool:
        import msvcrt

        handle = self.path.open("a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        deadline = time.monotonic() + 15
        while True:
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                self._handle = handle
                return True
            except OSError:
                if not wait or time.monotonic() >= deadline:
                    handle.close()
                    if wait:
                        raise TimeoutError(
                            "ParrotIA's Explorer queue is busy. Try again."
                        )
                    return False
                time.sleep(0.05)

    def release(self) -> None:
        if self._handle is not None:
            import msvcrt

            self._handle.seek(0)
            msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            self._handle.close()
            self._handle = None

    def __enter__(self):
        self.acquire(wait=True)
        return self

    def __exit__(self, *exc) -> None:
        self.release()


class ExplorerQueue:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.owner = _FileLock(directory / "owner.lock")
        # Serializes publication/ownership handoff with closing the last window.
        self.gate = _FileLock(directory / "routing.lock")

    def publish(self, paths: list[str]) -> None:
        request = self.directory / f"{time.time_ns():020d}-{uuid.uuid4().hex}.json"
        temporary = request.with_suffix(".tmp")
        temporary.write_text(json.dumps(paths, ensure_ascii=False), encoding="utf-8")
        temporary.replace(request)

    def take(self) -> list[str]:
        """Only the owner consumes requests; partial writes are never visible."""
        paths = []
        for request in sorted(self.directory.glob("*.json")):
            try:
                items = json.loads(request.read_text(encoding="utf-8"))
                if not isinstance(items, list) or not all(
                    isinstance(item, str) for item in items
                ):
                    raise ValueError("Invalid Explorer request")
                paths.extend(items)
            except (ValueError, UnicodeError):
                # Preserve malformed requests for diagnosis without blocking work.
                request.replace(request.with_suffix(".invalid"))
                continue
            request.unlink()
        return paths


def _save_transcript(source: Path, text: str) -> Path:
    """Reserve a unique filename, including for same-stem audio/video inputs."""
    index = 0
    while True:
        suffix = f" ({index})" if index else ""
        target = source.with_name(f"{source.stem}{suffix}.txt")
        try:
            stream = target.open("x", encoding="utf-8")
        except FileExistsError:
            index += 1
            continue
        try:
            with stream:
                stream.write(text)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return target


def _transcribe_files(
    paths: list[str],
    transcriber: Transcriber,
    cancel: threading.Event,
    events: queue.Queue,
) -> None:
    """Process a batch serially; failures never prevent the next file running."""
    for raw_path in paths:
        if cancel.is_set():
            break
        source = Path(raw_path)
        try:
            if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
                raise ValueError("Unsupported audio/video extension")

            def report(fraction: float, message: str, name=source.name) -> None:
                events.put(("progress", name, fraction, message))

            result = transcriber.transcribe(
                str(source), progress_callback=report, cancel_event=cancel
            )
            if cancel.is_set():
                break
            target = _save_transcript(source, formats.to_txt(result))
            events.put(("saved", str(target)))
        except TranscriptionCancelled:
            break
        except Exception as exc:  # noqa: BLE001 -- a bad file must not abort a selection
            events.put(("failed", str(source), str(exc)))
    events.put(("finished",))


def _run_window(requests: ExplorerQueue) -> None:
    # Keep Tk and CustomTkinter lazy: secondary invocations only publish paths.
    from tkinter import messagebox

    import customtkinter as ctk

    from .app import CORAL, GREEN, TEAL_DARK, WINDOW_BG
    from .resources import set_window_icon

    class ExplorerWindow(ctk.CTk):
        def __init__(self) -> None:
            super().__init__()
            self.title("Transcribe on Parrot")
            self.geometry("660x460")
            self.minsize(540, 360)
            self.configure(fg_color=WINDOW_BG)
            set_window_icon(self)
            self.engine = Transcriber()
            self.cancel = threading.Event()
            self.events: queue.Queue = queue.Queue()
            self.worker: threading.Thread | None = None
            self.closing = False
            self.saved = self.failed = 0
            ctk.CTkLabel(
                self,
                text="ParrotIA",
                font=("Segoe UI", 28, "bold"),
                text_color=GREEN,
            ).pack(anchor="w", padx=24, pady=(20, 4))
            ctk.CTkLabel(
                self,
                text="Transcripts save beside each source file.\n"
                "First use downloads the model; later runs work offline.",
                justify="left",
            ).pack(anchor="w", padx=24)
            self.status = ctk.CTkLabel(self, text="Preparing your files…", anchor="w")
            self.status.pack(fill="x", padx=24, pady=(16, 4))
            self.progress = ctk.CTkProgressBar(self, progress_color=GREEN)
            self.progress.pack(fill="x", padx=24, pady=8)
            self.progress.set(0)
            self.log = ctk.CTkTextbox(self, wrap="word")
            self.log.pack(fill="both", expand=True, padx=24, pady=8)
            self.log.configure(state="disabled")
            self.button = ctk.CTkButton(
                self, text="Cancel queue", fg_color=CORAL, command=self._cancel
            )
            self.button.pack(anchor="e", padx=24, pady=(4, 20))
            self.protocol("WM_DELETE_WINDOW", self._close)
            self.after(250, self._poll)

        def _append(self, text: str) -> None:
            self.log.configure(state="normal")
            self.log.insert("end", text + "\n\n")
            self.log.see("end")
            self.log.configure(state="disabled")

        def _cancel(self) -> None:
            with requests.gate:
                requests.take()
                self.cancel.set()
            self.status.configure(text="Cancelling… (model loading may take a moment)")

        def _close(self) -> None:
            busy = self.worker is not None and self.worker.is_alive()
            if busy and not messagebox.askyesno(
                "Cancel transcription?", "Cancel the remaining files and close?"
            ):
                return
            self.closing = True
            self._cancel()
            self.button.configure(state="disabled")

        def _poll(self) -> None:
            try:
                while True:
                    event = self.events.get_nowait()
                    if event[0] == "progress":
                        _, name, fraction, message = event
                        self.status.configure(text=f"{name}: {message}")
                        self.progress.set(fraction)
                    elif event[0] == "saved":
                        self.saved += 1
                        self._append(f"Saved: {event[1]}")
                    elif event[0] == "failed":
                        self.failed += 1
                        self._append(f"Failed: {event[1]}\n{event[2]}")
            except queue.Empty:
                pass

            if self.worker is None or not self.worker.is_alive():
                if self.closing:
                    # Publishers hold the same gate: a new request either belongs
                    # to the cancelled queue or elects a new owner after release.
                    with requests.gate:
                        requests.take()
                        requests.owner.release()
                        self.destroy()
                    return
                paths = requests.take()
                if paths:
                    self.cancel.clear()
                    self.button.configure(text="Cancel queue", fg_color=CORAL)
                    self.button.configure(command=self._cancel)
                    self.worker = threading.Thread(
                        target=_transcribe_files,
                        args=(paths, self.engine, self.cancel, self.events),
                        daemon=True,
                    )
                    self.worker.start()
                else:
                    state = "Cancelled" if self.cancel.is_set() else "Done"
                    self.status.configure(
                        text=f"{state} · {self.saved} saved · {self.failed} failed"
                    )
                    self.button.configure(
                        text="Close", fg_color=TEAL_DARK, command=self._close
                    )
            self.after(250, self._poll)

    ExplorerWindow().mainloop()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Transcribe Explorer selections.")
    parser.add_argument("files", nargs="+", help="Audio/video files to transcribe.")
    args = parser.parse_args(argv)
    if os.name != "nt":
        parser.error("Explorer integration is only available on Windows.")
    directory = Path(os.environ["LOCALAPPDATA"]) / "ParrotIA" / "explorer-queue"
    requests = ExplorerQueue(directory)
    with requests.gate:
        requests.publish([str(Path(path).resolve()) for path in args.files])
        if not requests.owner.acquire():
            return 0
    try:
        _run_window(requests)
    finally:
        requests.owner.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
