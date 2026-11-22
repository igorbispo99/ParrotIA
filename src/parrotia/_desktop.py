"""Linux desktop appearance detection without blocking Tk's event loop."""

from __future__ import annotations

import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional


def _desktop_command(name: str) -> str:
    snap = os.environ.get("SNAP")
    return str(Path(snap) / "usr/bin" / name) if snap else name


def _read(command: list[str]) -> Optional[str]:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=1.5, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def linux_appearance() -> Optional[str]:
    """Prefer the sandbox-aware portal, then support older GNOME desktops."""
    for method in ("ReadOne", "Read"):
        output = _read(
            [
                _desktop_command("gdbus"),
                "call",
                "--session",
                "--timeout",
                "1",
                "--dest",
                "org.freedesktop.portal.Desktop",
                "--object-path",
                "/org/freedesktop/portal/desktop",
                "--method",
                f"org.freedesktop.portal.Settings.{method}",
                "org.freedesktop.appearance",
                "color-scheme",
            ]
        )
        if output is not None:
            value = re.search(r"\buint32\s+(\d+)\b", output)
            if value and value[1] in ("1", "2"):
                return "Dark" if value[1] == "1" else "Light"
            # A successful response with no preference needs no legacy retry.
            break
    for key in ("color-scheme", "gtk-theme"):
        output = _read(
            [_desktop_command("gsettings"), "get", "org.gnome.desktop.interface", key]
        )
        if output is None:
            continue
        value = output.strip("'\"").lower()
        if key == "color-scheme":
            if value == "prefer-dark":
                return "Dark"
            if value == "prefer-light":
                return "Light"
        else:
            return "Dark" if "dark" in value else "Light"
    return None


class AppearanceWatcher:
    """Send changed preferences to a queue; never call Tk from this thread."""

    def __init__(
        self,
        publish: Callable[[str], None],
        initial: Optional[str],
        reader: Callable[[], Optional[str]] = linux_appearance,
        interval: float = 2.0,
    ) -> None:
        self._stop = threading.Event()

        def watch() -> None:
            previous = initial
            while not self._stop.wait(interval):
                mode = reader()
                if mode is not None and mode != previous and not self._stop.is_set():
                    publish(mode)
                    previous = mode

        self._thread = threading.Thread(
            target=watch, name="ParrotIA desktop appearance", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
