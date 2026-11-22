"""Shared packaged UI assets (also available in PyInstaller bundles)."""

import os
import subprocess
import sys
import webbrowser
from pathlib import Path

PROJECT_URL = "https://github.com/igorbispo99/ParrotIA"
PRIVACY_URL = f"{PROJECT_URL}/blob/main/docs/privacy.md"
LICENSE_URL = f"{PROJECT_URL}/blob/main/LICENSE"
NOTICES_NAME = "THIRD_PARTY_NOTICES.txt"


def bundled_notices() -> "Path | None":
    """The third-party notices file that installers place beside the executable."""
    if not getattr(sys, "frozen", False):
        return None
    path = Path(sys.executable).resolve().parent / NOTICES_NAME
    return path if path.is_file() else None


def open_path(path: Path) -> None:
    """Open a local file with the platform's default application."""
    if sys.platform == "win32":
        os.startfile(str(path))  # noqa: S606 - a file we ship, not user input
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def open_url(url: str) -> None:
    webbrowser.open(url)


def set_window_icon(window) -> None:
    assets = Path(__file__).with_name("assets")
    if sys.platform == "win32":
        window.iconbitmap(str(assets / "parrotia.ico"))
        # CustomTkinter schedules its default icon after constructing a window.
        window.after(250, lambda: window.iconbitmap(str(assets / "parrotia.ico")))
