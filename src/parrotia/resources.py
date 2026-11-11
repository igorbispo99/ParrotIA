"""Shared packaged UI assets (also available in PyInstaller bundles)."""

import sys
from pathlib import Path


def set_window_icon(window) -> None:
    assets = Path(__file__).with_name("assets")
    if sys.platform == "win32":
        window.iconbitmap(str(assets / "parrotia.ico"))
        # CustomTkinter schedules its default icon after constructing a window.
        window.after(250, lambda: window.iconbitmap(str(assets / "parrotia.ico")))
