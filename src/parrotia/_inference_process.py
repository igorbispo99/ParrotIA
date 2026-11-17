"""Keep macOS native inference and its lifetime separate from the Tk process."""

from __future__ import annotations

import multiprocessing
import threading
import time
from typing import Optional

from .transcriber import Transcriber, TranscriptionCancelled


def _worker_main(connection, cancelled, backend: str) -> None:
    """Own all native models on one child thread, including their destruction."""
    engine = Transcriber(backend=backend)
    try:
        while True:
            request = connection.recv()
            if request is None:
                return
            path, settings = request
            try:
                result = engine.transcribe(
                    path,
                    **settings,
                    cancel_event=cancelled,
                    progress_callback=lambda fraction, message: connection.send(
                        ("progress", fraction, message)
                    ),
                )
                connection.send(("result", result))
            except TranscriptionCancelled:
                connection.send(("cancelled",))
            except Exception as exc:
                connection.send(("error", str(exc)))
    except (EOFError, BrokenPipeError):
        pass
    finally:
        engine.close()
        connection.close()


class ProcessTranscriber(Transcriber):
    """A persistent, cancellable model process for the desktop app.

    Native model loading, language detection and decoding may hold Python's GIL.
    A separate process keeps Tk responsive during each of those stages. Closing
    first requests cancellation and cleanup, then terminates an unresponsive
    child after a bounded grace period. The GUI never owns Metal resources.
    """

    isolated = True
    _SHUTDOWN_TIMEOUT = 1.5

    def __init__(self, backend: Optional[str] = None) -> None:
        super().__init__(backend=backend)
        self._context = multiprocessing.get_context("spawn")
        self._process = None
        self._connection = None
        self._cancelled = None
        self._state_lock = threading.Lock()
        self._call_lock = threading.Lock()
        self._closed = False

    def _ensure_worker(self):
        with self._state_lock:
            if self._closed:
                raise TranscriptionCancelled()
            if self._process is not None and not self._process.is_alive():
                self._connection.close()
                self._process.join()
                self._process = self._connection = self._cancelled = None
            if self._process is None:
                parent, child = self._context.Pipe()
                cancelled = self._context.Event()
                process = self._context.Process(
                    target=_worker_main,
                    args=(child, cancelled, self.backend),
                    daemon=True,
                    name="ParrotIA inference",
                )
                try:
                    process.start()
                except BaseException:
                    parent.close()
                    child.close()
                    raise
                child.close()
                self._process = process
                self._connection = parent
                self._cancelled = cancelled
            return self._process, self._connection, self._cancelled

    def transcribe(
        self, audio_path: str, *, progress_callback=None, cancel_event=None, **settings
    ):
        with self._call_lock:
            if cancel_event is not None and cancel_event.is_set():
                raise TranscriptionCancelled()
            process, connection, cancelled = self._ensure_worker()
            cancelled.clear()
            finished = False
            cancel_started = None
            try:
                connection.send((audio_path, settings))
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        cancelled.set()
                        if cancel_started is None:
                            cancel_started = time.monotonic()
                        elif (
                            time.monotonic() - cancel_started >= self._SHUTDOWN_TIMEOUT
                        ):
                            raise TranscriptionCancelled()
                    if self._closed:
                        raise TranscriptionCancelled()
                    if not connection.poll(0.05):
                        if not process.is_alive():
                            raise RuntimeError(
                                "The transcription worker stopped unexpectedly "
                                f"(exit code {process.exitcode}). Try the CPU device "
                                "or a smaller model."
                            )
                        continue
                    event = connection.recv()
                    if event[0] == "progress":
                        if progress_callback is not None:
                            progress_callback(event[1], event[2])
                    elif event[0] == "cancelled":
                        finished = True
                        raise TranscriptionCancelled()
                    elif event[0] == "error":
                        finished = True
                        raise RuntimeError(event[1])
                    elif event[0] == "result":
                        finished = True
                        if cancelled.is_set():
                            raise TranscriptionCancelled()
                        return event[1]
            except (EOFError, OSError) as exc:
                if self._closed or (cancel_event is not None and cancel_event.is_set()):
                    raise TranscriptionCancelled() from exc
                raise RuntimeError(
                    "The transcription worker stopped unexpectedly. "
                    "Try the CPU device or a smaller model."
                ) from exc
            finally:
                # A crashed worker is discarded so the next job can start fresh.
                if not self._closed and (not finished or not process.is_alive()):
                    with self._state_lock:
                        connection.close()
                        if process.is_alive():
                            process.terminate()
                        process.join()
                        self._process = self._connection = self._cancelled = None

    def close(self) -> None:
        """Cancel work, release models, and reap the child before GUI teardown."""
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
            process, connection, cancelled = (
                self._process,
                self._connection,
                self._cancelled,
            )
        if process is None:
            return
        cancelled.set()
        try:
            connection.send(None)
        except (OSError, EOFError):
            pass
        process.join(self._SHUTDOWN_TIMEOUT)
        if process.is_alive():
            process.terminate()
            process.join(self._SHUTDOWN_TIMEOUT)
        if process.is_alive():
            process.kill()
            process.join()
        connection.close()
