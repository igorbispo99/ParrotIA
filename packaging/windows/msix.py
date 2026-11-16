"""Build the Microsoft Store MSIX package from the frozen PyInstaller bundle.

The Store re-signs MSIX packages itself, so the output is unsigned. Local
install tests sign a copy (see test-msix.ps1). Run through ``build.py --msix``,
or directly against an existing bundle::

    python packaging/windows/msix.py --bundle dist/ParrotIA
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Iterable, List, Tuple
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape, quoteattr

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
IDENTITY_FILE = HERE / "msix" / "identity.json"
TEMPLATE_FILE = HERE / "msix" / "AppxManifest.xml.in"

EXECUTABLE = "parrotia-gui.exe"
APPLICATION_ID = "ParrotIA"
# Distinct from pip's parrotia/parrotia-gui scripts, which may also be on PATH.
ALIAS = "parrotia-app.exe"
VERB_TITLE = "Transcribe on Parrot"
# Windows 10 2004: packaged Explorer commands (desktop4/desktop5 context menus)
# need 1903+, and every Windows 10 release still in service is 22H2 anyway.
MIN_VERSION = "10.0.19041.0"
MAX_VERSION_TESTED = "10.0.26100.0"

# The IExplorerCommand behind "Transcribe on Parrot" in Windows 11's main
# context menu. Never change the CLSID: Explorer caches handlers by it.
SHELL_SOURCE = HERE / "shell"
SHELL_DLL = "parrotia_shell.dll"
SHELL_CLSID = "A62953B0-E72C-49CD-B8AC-09742C34D586"

# (file name, width, height, badge share of the shorter side)
_SCALES = {100: 1.0, 125: 1.25, 150: 1.5, 200: 2.0, 400: 4.0}
ASSETS: List[Tuple[str, int, int, float]] = (
    [
        (f"Square44x44Logo.scale-{s}.png", round(44 * f), round(44 * f), 1.0)
        for s, f in _SCALES.items()
    ]
    + [
        (f"Square44x44Logo.targetsize-{t}{suffix}.png", t, t, 1.0)
        for t in (16, 24, 32, 48, 256)
        for suffix in ("", "_altform-unplated")
    ]
    + [
        (f"Square150x150Logo.scale-{s}.png", round(150 * f), round(150 * f), 0.66)
        for s, f in _SCALES.items()
    ]
    + [
        (f"Wide310x150Logo.scale-{s}.png", round(310 * f), round(150 * f), 0.8)
        for s, f in _SCALES.items()
    ]
    + [
        (f"StoreLogo.scale-{s}.png", round(50 * f), round(50 * f), 1.0)
        for s, f in _SCALES.items()
    ]
)


@dataclass(frozen=True)
class Identity:
    name: str
    publisher: str
    publisher_display_name: str
    placeholder: bool = False


def load_identity(path: Path = IDENTITY_FILE) -> Identity:
    data = json.loads(path.read_text(encoding="utf-8"))
    identity = Identity(
        name=data["name"],
        publisher=data["publisher"],
        publisher_display_name=data["publisher_display_name"],
        placeholder=bool(data.get("placeholder", False)),
    )
    # Package names: 3-50 characters of letters, digits, periods and dashes.
    if not re.fullmatch(r"[A-Za-z0-9.\-]{3,50}", identity.name):
        raise ValueError(f"Invalid package identity name: {identity.name!r}")
    if not identity.publisher.startswith("CN="):
        raise ValueError(
            f"Publisher must be a distinguished name: {identity.publisher!r}"
        )
    return identity


def msix_version(version: str) -> str:
    """Map ``1.4.1`` to the Store's ``1.4.1.0``; the fourth field must stay 0."""
    parts = version.split(".")
    if not 1 <= len(parts) <= 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Expected a numeric X.Y.Z version, got {version!r}")
    numbers = [int(p) for p in parts] + [0] * (3 - len(parts))
    if numbers[0] == 0 or any(n > 65535 for n in numbers):
        raise ValueError(f"Version {version!r} is outside the MSIX range")
    return ".".join(str(n) for n in numbers + [0])


def _media_types(extensions: Iterable[str]) -> List[str]:
    types = sorted({ext.lower() for ext in extensions})
    if not types or not all(re.fullmatch(r"\.[a-z0-9]+", ext) for ext in types):
        raise ValueError(f"Invalid file extensions: {types!r}")
    return types


def render_manifest(identity: Identity, version: str, extensions: Iterable[str]) -> str:
    types = _media_types(extensions)
    attribute = lambda value: quoteattr(value)[1:-1]  # noqa: E731 -- quoted in template
    return Template(TEMPLATE_FILE.read_text(encoding="utf-8")).substitute(
        name=attribute(identity.name),
        publisher=attribute(identity.publisher),
        publisher_display_name=escape(identity.publisher_display_name),
        version=msix_version(version),
        min_version=MIN_VERSION,
        max_version_tested=MAX_VERSION_TESTED,
        executable=EXECUTABLE,
        application_id=APPLICATION_ID,
        alias=ALIAS,
        shell_dll=SHELL_DLL,
        shell_clsid=SHELL_CLSID,
        file_types="\n".join(
            f"              <uap:FileType>{ext}</uap:FileType>" for ext in types
        ),
    )


def render_shell_config(extensions: Iterable[str]) -> str:
    """C++ header shared by the Explorer command and its test."""
    types = ", ".join(f'L"{ext}"' for ext in _media_types(extensions))
    return (
        "// Generated by packaging/windows/msix.py. Do not edit.\n"
        "#pragma once\n"
        f'#define PARROTIA_SHELL_CLSID "{SHELL_CLSID}"\n'
        f'static const wchar_t kTitle[] = L"{VERB_TITLE}";\n'
        f'static const wchar_t kExecutable[] = L"{EXECUTABLE}";\n'
        f'static const wchar_t kApplicationId[] = L"{APPLICATION_ID}";\n'
        f"static const wchar_t* const kSupportedExtensions[] = {{{types}}};\n"
    )


def find_vcvars() -> Path:
    """Locate vcvars64.bat of a Visual Studio install with the C++ x64 tools."""
    roots = [os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")]
    for root in filter(None, roots):
        vswhere = Path(root) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
        if not vswhere.is_file():
            continue
        result = subprocess.run(
            [
                str(vswhere), "-latest", "-products", "*", "-requires",
                "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                "-property", "installationPath",
            ],
            capture_output=True, text=True, check=False,
        )  # fmt: skip
        for line in result.stdout.splitlines():
            vcvars = Path(line.strip()) / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
            if vcvars.is_file():
                return vcvars
    raise SystemExit(
        "Visual Studio C++ build tools (x64) not found; they build the Explorer "
        "command DLL. Install the 'Desktop development with C++' workload."
    )


def build_shell_extension(work: Path, extensions: Iterable[str]) -> Path:
    """Compile the Explorer command DLL and run its checks; return the DLL."""
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    (work / "shell_config.h").write_text(
        render_shell_config(extensions), encoding="utf-8"
    )
    flags = "/nologo /utf-8 /std:c++17 /O2 /EHsc /W4 /WX /DUNICODE /D_UNICODE /I ."
    source = SHELL_SOURCE
    script = work / "build.bat"
    script.write_text(
        "@echo off\r\n"
        f'call "{find_vcvars()}" >nul || exit /b 1\r\n'
        f'cl {flags} /LD "{source / "parrotia_shell.cpp"}" /Fe{SHELL_DLL} '
        f'/link /DEF:"{source / "parrotia_shell.def"}" '
        "ole32.lib shell32.lib shlwapi.lib runtimeobject.lib || exit /b 1\r\n"
        f'cl {flags} "{source / "shell_test.cpp"}" /Feshell_test.exe '
        "/link ole32.lib shell32.lib || exit /b 1\r\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["cmd", "/d", "/c", script.name],
        cwd=work, capture_output=True, text=True, errors="replace", check=False,
    )  # fmt: skip
    if result.returncode:
        raise SystemExit(
            f"Explorer command build failed:\n{result.stdout}\n{result.stderr}"
        )
    dll = work / SHELL_DLL
    # The checks create files, so use a scratch folder outside the protected
    # folders Controlled folder access guards (the repository may be in one).
    with tempfile.TemporaryDirectory(prefix="parrotia-shell-") as scratch:
        check = subprocess.run(
            [str(work / "shell_test.exe"), str(dll), scratch],
            capture_output=True, text=True, errors="replace", check=False,
        )  # fmt: skip
    if check.returncode:
        raise SystemExit(
            f"Explorer command checks failed:\n{check.stdout}{check.stderr}"
        )
    print(check.stdout.strip().splitlines()[-1])
    return dll


def _badge():
    sys.path.insert(0, str(HERE))
    try:
        from make_icon import draw_badge
    finally:
        sys.path.remove(str(HERE))
    return draw_badge()


def write_store_icon(path: Path, size: int = 300) -> Path:
    """The 1:1 tile icon Partner Center asks for in the Store listing."""
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    _badge().resize((size, size), Image.Resampling.LANCZOS).save(path)
    return path


def write_assets(destination: Path) -> List[Path]:
    """Render tile, Start and taskbar logos from the vector-style badge."""
    from PIL import Image

    badge = _badge()
    destination.mkdir(parents=True, exist_ok=True)
    written = []
    for name, width, height, share in ASSETS:
        side = max(1, round(min(width, height) * share))
        canvas = Image.new("RGBA", (width, height))
        mark = badge.resize((side, side), Image.Resampling.LANCZOS)
        canvas.paste(mark, ((width - side) // 2, (height - side) // 2), mark)
        path = destination / name
        canvas.save(path)
        written.append(path)
    return written


def find_sdk_tool(name: str) -> Path:
    """Locate a Windows SDK tool (newest x64 build), or one on PATH."""
    found = shutil.which(name)
    if found:
        return Path(found)
    roots = [os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")]
    candidates = []
    for root in filter(None, roots):
        bin_dir = Path(root) / "Windows Kits" / "10" / "bin"
        candidates += bin_dir.glob(f"10.*/x64/{name}")
    if not candidates:
        raise SystemExit(f"{name} not found. Install the Windows 10/11 SDK.")

    def sdk_version(path: Path) -> Tuple[int, ...]:
        return tuple(int(p) for p in path.parent.parent.name.split("."))

    return max(candidates, key=sdk_version)


def _run(command: List[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise SystemExit(
            f"{Path(command[0]).name} failed ({result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )


def make_resources(staging: Path) -> Path:
    """Index the qualified assets (scale/targetsize) into resources.pri."""
    makepri = str(find_sdk_tool("makepri.exe"))
    config = staging / "priconfig.xml"
    _run(
        [
            makepri,
            "createconfig",
            "/cf",
            str(config),
            "/dq",
            "en-US",
            "/pv",
            "10.0.0",
            "/o",
        ]
    )
    # The default config splits non-default scales into separate resource
    # packages, which only bundles carry. A single .msix needs one index.
    tree = ET.parse(config)
    for parent in tree.iter():
        for packaging in parent.findall("packaging"):
            parent.remove(packaging)
    tree.write(config, encoding="utf-8", xml_declaration=True)
    output = staging / "resources.pri"
    _run(
        [
            makepri,
            "new",
            "/pr",
            str(staging),
            "/cf",
            str(config),
            "/mn",
            str(staging / "AppxManifest.xml"),
            "/of",
            str(output),
            "/o",
        ]
    )
    return output


def build_layout(
    bundle: Path, layout: Path, manifest: str, extra_files: Iterable[Path] = ()
) -> None:
    if not (bundle / EXECUTABLE).is_file():
        raise SystemExit(f"Frozen bundle not found: {bundle / EXECUTABLE}")
    if layout.exists():
        shutil.rmtree(layout)
    # Index only the manifest and logos; the bundle's thousands of files are
    # not resources and would bloat resources.pri.
    staging = layout.with_name(layout.name + "-pri")
    if staging.exists():
        shutil.rmtree(staging)
    (staging / "Assets").mkdir(parents=True)
    (staging / "AppxManifest.xml").write_text(manifest, encoding="utf-8")
    write_assets(staging / "Assets")
    make_resources(staging)
    shutil.copytree(bundle, layout)
    shutil.copytree(staging / "Assets", layout / "Assets")
    shutil.copy2(staging / "resources.pri", layout / "resources.pri")
    for extra in extra_files:
        shutil.copy2(extra, layout / extra.name)
    (layout / "AppxManifest.xml").write_text(manifest, encoding="utf-8")
    shutil.rmtree(staging)


def pack(layout: Path, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            str(find_sdk_tool("makeappx.exe")),
            "pack",
            "/o",
            "/h",
            "SHA256",
            "/d",
            str(layout),
            "/p",
            str(output),
        ]
    )
    return output


def build(
    bundle: Path,
    version: str,
    extensions: Iterable[str],
    identity: Identity,
    work: Path = ROOT / "build/windows/msix",
    output_dir: Path = ROOT / "dist/msix",
) -> Path:
    extensions = list(extensions)
    manifest = render_manifest(identity, version, extensions)
    shell_dll = build_shell_extension(work / "shell", extensions)
    layout = work / "layout"
    build_layout(bundle, layout, manifest, [shell_dll])
    output = pack(layout, output_dir / f"ParrotIA-{version}-windows-x64.msix")
    write_store_icon(output_dir / "ParrotIA-store-icon-300.png")
    if identity.placeholder:
        print(
            "WARNING: packaging/windows/msix/identity.json still holds placeholder "
            "values. This MSIX is for local testing, not Store submission."
        )
    print(f"MSIX: {output}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bundle", type=Path, default=ROOT / "dist/ParrotIA")
    parser.add_argument("--identity", type=Path, default=IDENTITY_FILE)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist/msix")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "src"))
    from parrotia import __version__
    from parrotia.transcriber import SUPPORTED_EXTENSIONS

    build(
        args.bundle.resolve(),
        __version__,
        SUPPORTED_EXTENSIONS,
        load_identity(args.identity),
        output_dir=args.output_dir.resolve(),
    )


if __name__ == "__main__":
    main()
