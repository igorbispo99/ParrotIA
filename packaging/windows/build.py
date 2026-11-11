"""Build a self-contained x64 Windows bundle and per-user Inno Setup installer."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from parrotia import __version__  # noqa: E402
from parrotia.transcriber import SUPPORTED_EXTENSIONS  # noqa: E402


def registry_entries() -> str:
    lines = []
    for extension in SUPPORTED_EXTENSIONS:
        key = rf"Software\Classes\SystemFileAssociations\{extension}\shell\ParrotIA.Transcribe"
        prefix = f'Root: HKCU; Subkey: "{key}"; '
        lines.extend(
            [
                prefix + 'ValueType: string; ValueName: ""; '
                'ValueData: "Transcribe on Parrot"; Tasks: explorer; Flags: uninsdeletekey',
                prefix + 'ValueType: string; ValueName: "Icon"; '
                r'ValueData: """{app}\parrotia-gui.exe"",0"; Tasks: explorer',
                prefix + 'ValueType: string; ValueName: "MultiSelectModel"; '
                'ValueData: "Player"; Tasks: explorer',
                prefix + 'ValueType: string; ValueName: "NeverDefault"; '
                'ValueData: ""; Tasks: explorer',
                (
                    rf'Root: HKCU; Subkey: "{key}\command"; ValueType: string; ValueName: ""; '
                    r'ValueData: """{app}\parrotia-gui.exe"" --shell ""%1"""; Tasks: explorer'
                ),
            ]
        )
    return "\n".join(lines) + "\n"


def find_compiler() -> str:
    compiler = shutil.which("ISCC.exe")
    if compiler:
        return compiler
    for location in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = Path(os.environ.get(location, "C:/"))
        for relative in (
            "Inno Setup 7/ISCC.exe",
            "Programs/Inno Setup 7/ISCC.exe",
            "Inno Setup 6/ISCC.exe",
            "Programs/Inno Setup 6/ISCC.exe",
        ):
            candidate = base / relative
            if candidate.is_file():
                return str(candidate)
    raise SystemExit(
        "Install Inno Setup 6 or newer, or pass --iscc <path-to-ISCC.exe>."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iscc", help="Path to the Inno Setup 6 compiler.")
    parser.add_argument("--bundle-only", action="store_true")
    args = parser.parse_args()
    if sys.platform != "win32" or sys.maxsize <= 2**32:
        parser.error("Build with 64-bit Python on Windows.")
    compiler = None if args.bundle_only else (args.iscc or find_compiler())
    generated = ROOT / "build/windows"
    generated.mkdir(parents=True, exist_ok=True)
    registry = generated / "file-associations.iss"
    registry.write_text(registry_entries(), encoding="utf-8")
    version = tuple(int(part) for part in __version__.split(".")) + (0,)
    (generated / "version-info.txt").write_text(
        "VSVersionInfo(ffi=FixedFileInfo("
        f"filevers={version!r}, prodvers={version!r}, mask=0x3f, flags=0, "
        "OS=0x40004, fileType=1, subtype=0, date=(0, 0)), "
        "kids=[StringFileInfo([StringTable('040904B0', ["
        "StringStruct('CompanyName', 'Igor Bispo'), "
        "StringStruct('FileDescription', 'ParrotIA local transcription'), "
        f"StringStruct('FileVersion', '{__version__}'), "
        "StringStruct('ProductName', 'ParrotIA'), "
        f"StringStruct('ProductVersion', '{__version__}')"
        "]) ]), VarFileInfo([VarStruct('Translation', [1033, 1200])])])",
        encoding="utf-8",
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(ROOT / "dist"),
            "--workpath",
            str(generated / "pyinstaller"),
            str(ROOT / "packaging/ParrotIA.spec"),
        ],
        cwd=ROOT,
        check=True,
    )
    # Check the actual frozen executable, not the developer's Python environment.
    report = generated / "smoke-test.json"
    result = subprocess.run(
        [
            str(ROOT / "dist/ParrotIA/parrotia-gui.exe"),
            "--smoke-test",
            str(report),
        ],
        cwd=generated,
        timeout=120,
        check=False,
    )
    if result.returncode:
        raise SystemExit(
            report.read_text(encoding="utf-8")
            if report.exists()
            else f"Frozen app failed (exit {result.returncode})."
        )
    print(report.read_text(encoding="utf-8"))
    if compiler:
        subprocess.run(
            [
                compiler,
                f"/DAppVersion={__version__}",
                f"/DRegistryFile={registry}",
                str(ROOT / "packaging/windows/installer.iss"),
            ],
            cwd=ROOT,
            check=True,
        )
        print(f"Installer: {ROOT / 'dist/installer'}")


if __name__ == "__main__":
    main()
