"""Mount a DMG, copy its app to a temporary folder and test the installed copy."""

from __future__ import annotations

import json
import plistlib
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    dmgs = list((ROOT / "dist/installer").glob("*-macos-*.dmg"))
    if len(dmgs) != 1:
        raise SystemExit("Expected exactly one macOS DMG in dist/installer")
    with tempfile.TemporaryDirectory(prefix="parrotia-install-test-") as tmp:
        folder = Path(tmp)
        mount = folder / "mounted"
        subprocess.run(
            [
                "hdiutil",
                "attach",
                "-readonly",
                "-nobrowse",
                "-mountpoint",
                str(mount),
                str(dmgs[0]),
            ],
            check=True,
        )
        try:
            assert (mount / "Applications").is_symlink()
            app = folder / "ParrotIA.app"
            shutil.copytree(mount / app.name, app, symlinks=True)
        finally:
            subprocess.run(["hdiutil", "detach", str(mount)], check=True)
        with (app / "Contents/Info.plist").open("rb") as handle:
            info = plistlib.load(handle)
        assert info["CFBundleIdentifier"] == "io.github.igorbispo99.ParrotIA"
        report = folder / "report.json"
        subprocess.run(
            [str(app / "Contents/MacOS/parrotia-gui"), "--smoke-test", str(report)],
            check=True,
        )
        data = json.loads(report.read_text(encoding="utf-8"))
        assert data["backend"] == "whisper.cpp" and data["samples"] == 1600
        print("Disk image installation verified:", data)


if __name__ == "__main__":
    main()
