"""Build the Snap's native runtime from hash-pinned, redistributable sources.

Run with Ubuntu 24.04 / Python 3.12. Original archives, build commands and
upstream notices are retained in the resulting Snap, alongside dynamic libraries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import urllib.request
import venv
from pathlib import Path


def verify(path: Path, expected: str) -> None:
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise ValueError(f"Source checksum mismatch: {path.name}: {actual}")


def extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    # Strip the single upstream top-level directory. Reject path traversal and
    # escaping links before extracting untrusted upstream archive members.
    with tarfile.open(archive) as source:
        members = source.getmembers()
        roots = {Path(m.name).parts[0] for m in members if Path(m.name).parts}
        if len(roots) != 1:
            raise ValueError(f"Expected one archive root: {archive.name}")
        for member in members:
            parts = Path(member.name).parts
            if Path(member.name).is_absolute() or ".." in parts:
                raise ValueError(f"Unsafe archive member: {member.name}")
            if len(parts) == 1:
                continue
            member.name = str(Path(*parts[1:]))
            source.extract(member, destination, filter="data")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    args = parser.parse_args()
    install, work = args.install.resolve(), args.work.resolve()
    project = Path(__file__).resolve().parents[2]
    work.mkdir(parents=True, exist_ok=True)
    docs = install / "share/doc/parrotia/native"
    archives = docs / "sources"
    archives.mkdir(parents=True, exist_ok=True)
    lock = json.loads((project / "snap/native-sources.json").read_text())
    shutil.copy2(project / "snap/native-sources.json", docs)
    shutil.copy2(project / "snap/build-requirements.txt", docs)
    shutil.copy2(__file__, docs)
    for path in (project / "snap/licenses").glob("ffmpeg-*.asc"):
        shutil.copy2(path, docs)
    commands = []
    env = os.environ.copy()
    # Keep this bounded on shared workstations and hosted CI runners.
    jobs = str(min(4, os.cpu_count() or 1))
    env["CMAKE_BUILD_PARALLEL_LEVEL"] = jobs
    env["NPY_NUM_BUILD_JOBS"] = jobs
    env["SOURCE_DATE_EPOCH"] = "1794441600"
    log = (docs / "build.log").open("a", encoding="utf-8")

    def run(command: list, cwd: Path = work, extra: dict = None) -> None:
        command = [str(c) for c in command]
        print("Building:", " ".join(command), flush=True)
        commands.append({"argv": command, "cwd": str(cwd), "environment": extra or {}})
        (docs / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        subprocess.run(
            command,
            cwd=cwd,
            env={**env, **(extra or {})},
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )
        log.flush()

    for entry in lock["sources"]:
        archive = archives / entry["name"]
        if not archive.exists():
            print("Fetching pinned source:", entry["name"], flush=True)
            with urllib.request.urlopen(entry["url"], timeout=120) as response:
                with archive.open("wb") as output:
                    shutil.copyfileobj(response, output)
        verify(archive, entry["sha256"])
        destination = work / "source" / entry["destination"]
        if not destination.exists() or not any(destination.iterdir()):
            extract(archive, destination)
    source = work / "source"
    buildenv = work / "build-env"
    if not buildenv.exists():
        venv.create(buildenv, with_pip=True)
    python = buildenv / "bin/python"
    run([python, "-m", "pip", "install", "-r", project / "snap/build-requirements.txt"])
    env["PATH"] = str(buildenv / "bin") + os.pathsep + env["PATH"]
    wheels = install / "share/parrotia/native-wheels"
    wheels.mkdir(parents=True, exist_ok=True)
    ffbuild = work / ("ffmpeg-" + lock["versions"]["ffmpeg"] + "-build")
    ffbuild.mkdir(exist_ok=True)
    ffargs = [
        source / lock["sources"][0]["destination"] / "configure",
        "--prefix=/usr",
        "--libdir=/usr/lib",
        "--enable-shared",
        "--disable-static",
        "--enable-pic",
        "--disable-autodetect",
        "--disable-programs",
        "--disable-doc",
        "--disable-debug",
        "--disable-network",
    ]
    run(ffargs, ffbuild)
    run(["make", "-j" + jobs], ffbuild)
    run(["make", "install", "DESTDIR=" + str(install)], ffbuild)
    shutil.copy2(ffbuild / "config.h", docs / "ffmpeg-config.h")
    shutil.copy2(ffbuild / "ffbuild/config.mak", docs / "ffmpeg-config.mak")
    # Permissively licensed CPU backend, with no proprietary GPU/BLAS or
    # privately bundled GCC/Fortran runtime libraries.
    ctbuild = work / "ctranslate2-build"
    run(
        [
            "cmake",
            "-S",
            source / "ctranslate2",
            "-B",
            ctbuild,
            "-G",
            "Ninja",
            "-DCMAKE_BUILD_TYPE=Release",
            "-DCMAKE_INSTALL_PREFIX=/usr",
            "-DCMAKE_INSTALL_LIBDIR=lib",
            "-DBUILD_CLI=OFF",
            "-DBUILD_TESTS=OFF",
            "-DWITH_MKL=OFF",
            "-DWITH_DNNL=OFF",
            "-DWITH_OPENBLAS=OFF",
            "-DWITH_RUY=ON",
            "-DOPENMP_RUNTIME=NONE",
            "-DWITH_CUDA=OFF",
            "-DWITH_CUDNN=OFF",
            "-DRUY_MINIMAL_BUILD=ON",
        ]
    )
    run(["cmake", "--build", ctbuild, "--parallel", jobs])
    run(["cmake", "--install", ctbuild], extra={"DESTDIR": str(install)})
    shutil.copy2(ctbuild / "CMakeCache.txt", docs / "ctranslate2-CMakeCache.txt")
    native_env = {
        "LD_LIBRARY_PATH": str(install / "usr/lib"),
        "PKG_CONFIG_LIBDIR": str(install / "usr/lib/pkgconfig"),
        "PKG_CONFIG_SYSROOT_DIR": str(install),
        "CTRANSLATE2_ROOT": str(install / "usr"),
    }
    run(
        [python, "-m", "build", "--wheel", "--no-isolation", "--outdir", wheels],
        source / "ctranslate2/python",
        native_env,
    )
    run(
        [python, "-m", "build", "--wheel", "--no-isolation", "--outdir", wheels],
        source / "av",
        native_env,
    )
    # C fallback LAPACK keeps NumPy usable without a wheel's opaque Fortran
    # runtimes. Whisper's matrix multiplication is handled by CTranslate2.
    run(
        [
            python,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            wheels,
            "-Csetup-args=-Dblas=",
            "-Csetup-args=-Dlapack=",
            "-Csetup-args=-Dallow-noblas=true",
            "-Ccompile-args=-j" + jobs,
        ],
        source / "numpy",
    )
    # Remove build-machine RPATHs and regenerate each wheel's RECORD correctly.
    for wheel in sorted(wheels.glob("*.whl")):
        unpack = work / ("unpack-" + wheel.name.split("-")[0])
        run([python, "-m", "wheel", "unpack", wheel, "-d", unpack])
        directory = next(unpack.iterdir())
        for binary in directory.rglob("*.so*"):
            if binary.is_file() and binary.read_bytes()[:4] == b"\x7fELF":
                run(["patchelf", "--remove-rpath", binary])
        run([python, "-m", "wheel", "pack", directory, "-d", wheels])
    notices = docs / "notices"
    for component in [lock["sources"][0]["destination"], "ctranslate2", "av", "numpy"]:
        for path in (source / component).rglob("*"):
            if path.is_file() and any(
                x in path.name.lower()
                for x in ["license", "licence", "copying", "notice", "copyright"]
            ):
                relative = path.relative_to(source)
                target = notices / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
    run([python, "-m", "pip", "freeze"])
    print(
        "Native runtime and complete corresponding source archives staged", flush=True
    )


if __name__ == "__main__":
    main()
