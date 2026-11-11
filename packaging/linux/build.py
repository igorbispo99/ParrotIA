"""Build self-contained Linux x86-64 DEB and RPM desktop packages.

Build on Ubuntu 22.04 (glibc 2.35) for compatibility with newer distributions.
Requires dpkg-deb, rpmbuild, and an X display (xvfb-run on CI).
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from parrotia import __version__  # noqa: E402


def stage_package(bundle: Path, stage: Path) -> None:
    """Stage only application-owned paths; never claim system directories."""
    shutil.copytree(bundle, stage / "opt/parrotia", symlinks=True)
    launchers = stage / "usr/bin"
    launchers.mkdir(parents=True)
    launcher = launchers / "parrotia-gui"
    launcher.write_text(
        '#!/bin/sh\nexec /opt/parrotia/parrotia-gui "$@"\n', encoding="utf-8"
    )
    launcher.chmod(0o755)
    applications = stage / "usr/share/applications"
    applications.mkdir(parents=True)
    shutil.copy2(ROOT / "packaging/linux/parrotia.desktop", applications)
    icons = stage / "usr/share/icons/hicolor/256x256/apps"
    icons.mkdir(parents=True)
    shutil.copy2(ROOT / "src/parrotia/assets/parrotia.png", icons)
    docs = stage / "usr/share/doc/parrotia"
    docs.mkdir(parents=True)
    shutil.copy2(ROOT / "LICENSE", docs / "copyright")


def build_deb(stage: Path, output: Path) -> None:
    control = stage / "DEBIAN"
    control.mkdir()
    size = sum(p.stat().st_size for p in stage.rglob("*") if p.is_file()) // 1024
    (control / "control").write_text(
        "Package: parrotia\n"
        f"Version: {__version__}\n"
        "Section: sound\nPriority: optional\nArchitecture: amd64\n"
        "Maintainer: Igor Bispo <igor.rabbit99@gmail.com>\n"
        f"Installed-Size: {size}\n"
        "Depends: libc6 (>= 2.35), libgcc-s1, libstdc++6, libgomp1, "
        "libx11-6, libxext6, libxrender1, libxft2, libxcb1, "
        "libfontconfig1, libfreetype6, libexpat1, zlib1g\n"
        "Homepage: https://github.com/igorbispo99/ParrotIA\n"
        "Description: Local audio and video transcription with Whisper\n"
        " Includes Python, the inference engine, and audio codecs.\n"
        " Models download on first use and are cached for offline transcription.\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            "dpkg-deb",
            "--build",
            "--root-owner-group",
            "-Zxz",
            "-z3",
            str(stage),
            str(output / f"parrotia_{__version__}_amd64.deb"),
        ],
        check=True,
    )


def build_rpm(stage: Path, output: Path, work: Path) -> None:
    top = work / "rpmbuild"
    for directory in ("BUILD", "BUILDROOT", "RPMS", "SOURCES", "SPECS", "SRPMS"):
        (top / directory).mkdir(parents=True, exist_ok=True)
    archive = shutil.make_archive(str(top / "SOURCES/payload"), "gztar", stage)
    spec = top / "SPECS/parrotia.spec"
    spec.write_text(
        "Name: parrotia\n"
        f"Version: {__version__}\nRelease: 1\n"
        "Summary: Local audio and video transcription with Whisper\n"
        "License: AGPL-3.0-or-later\n"
        "URL: https://github.com/igorbispo99/ParrotIA\n"
        f"Source0: {Path(archive).name}\nBuildArch: x86_64\n"
        # Private bundled libraries satisfy each other's ELF dependencies.
        # Auto-generation would incorrectly require them from system packages.
        "AutoReqProv: no\n"
        "Requires: /bin/sh, glibc >= 2.35, libgcc, libstdc++, libgomp, "
        "libX11, libXext, libXrender, libXft, libxcb, fontconfig, freetype, expat, zlib\n"
        # Bundles are already stripped by upstream wheel publishers. Rewriting
        # their ELF files can break PyInstaller's symlinked library layout.
        "%global debug_package %{nil}\n"
        "%global __os_install_post %{nil}\n"
        "%description\n"
        "Local transcription with bundled Python, Whisper inference and codecs.\n"
        "Models download on first use and are cached for offline transcription.\n"
        "%prep\n%build\n%install\n"
        "mkdir -p %{buildroot}\n"
        "tar -xzf %{SOURCE0} -C %{buildroot}\n"
        "%files\n%defattr(-,root,root,-)\n"
        "/opt/parrotia\n/usr/bin/parrotia-gui\n"
        "/usr/share/applications/parrotia.desktop\n"
        "/usr/share/icons/hicolor/256x256/apps/parrotia.png\n"
        "%doc /usr/share/doc/parrotia\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            "rpmbuild",
            "-bb",
            "--define",
            f"_topdir {top}",
            "--define",
            "_binary_payload w6.gzdio",
            str(spec),
        ],
        check=True,
    )
    packages = list((top / "RPMS").rglob("*.rpm"))
    if len(packages) != 1:
        raise RuntimeError(f"Expected one RPM, found {len(packages)}")
    shutil.copy2(packages[0], output)


def main() -> None:
    if sys.platform != "linux" or platform.machine() != "x86_64":
        raise SystemExit("Build on x86-64 Linux (Ubuntu 22.04 recommended).")
    for command in ("dpkg-deb", "rpmbuild"):
        if shutil.which(command) is None:
            raise SystemExit(f"Required build tool is missing: {command}")
    work = ROOT / "build/linux"
    work.mkdir(parents=True, exist_ok=True)
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
            str(work / "pyinstaller"),
            str(ROOT / "packaging/ParrotIA.spec"),
        ],
        cwd=ROOT,
        check=True,
    )
    bundle = ROOT / "dist/ParrotIA"
    report = work / "smoke-test.json"
    result = subprocess.run(
        [str(bundle / "parrotia-gui"), "--smoke-test", str(report)],
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
    # Each build gets fresh staging paths without deleting existing directories.
    import tempfile

    with tempfile.TemporaryDirectory(prefix="stage-", dir=work) as temporary:
        stage = Path(temporary) / "root"
        stage_package(bundle, stage)
        output = ROOT / "dist/installer"
        output.mkdir(parents=True, exist_ok=True)
        # Build RPM before adding Debian-only control metadata to the payload.
        build_rpm(stage, output, work)
        build_deb(stage, output)
    print(f"Linux installers: {output}")


if __name__ == "__main__":
    main()
