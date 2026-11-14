"""Replace bootstrap native wheels with the verified source-build outputs.

Only the application runtime is installed; converter/f2py developer entry points
are intentionally omitted. Product entry points remain owned by the Python plugin.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from importlib.metadata import distributions
from pathlib import Path

NATIVE = {"av", "numpy", "ctranslate2"}


def uninstall(dist, install: Path) -> None:
    paths = []
    for item in dist.files or []:
        path = Path(dist.locate_file(item))
        # Use lexical paths for file operations, resolve only for containment.
        # Refuse to follow RECORD entries outside the part's installation root.
        if not path.resolve().is_relative_to(install.resolve()):
            raise ValueError(f"Unsafe installed RECORD path: {item}")
        paths.append(path)
    for path in paths:
        if path.is_file() or path.is_symlink():
            path.unlink()
    # Remove now-empty directories, never recurse into unknown content.
    parents = {
        parent
        for path in paths
        for parent in path.parents
        if parent != install and parent.is_relative_to(install)
    }
    for parent in sorted(parents, key=lambda p: len(p.parts), reverse=True):
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()


def install_wheel(wheel: Path, site: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        members = archive.infolist()
        for member in members:
            path = Path(member.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or any(p.endswith(".data") for p in path.parts)
            ):
                raise ValueError(f"Unsupported native wheel member: {member.filename}")
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f"Native wheel contains a symlink: {member.filename}")
        archive.extractall(site)


def replace(install: Path, wheels: Path) -> None:
    sites = list(install.glob("lib/python*/site-packages"))
    if len(sites) != 1:
        raise ValueError("Expected exactly one Python site-packages directory")
    site = sites[0]
    candidates = {w.name.split("-")[0].lower(): w for w in wheels.glob("*.whl")}
    if set(candidates) != NATIVE:
        raise ValueError(
            f"Expected exactly the three native source-built wheels: {candidates}"
        )
    for dist in list(distributions(path=[str(site)])):
        if dist.metadata["Name"].lower() in NATIVE:
            uninstall(dist, install)
    for name, wheel in sorted(candidates.items()):
        install_wheel(wheel, site)
        print("Installed source-built runtime:", name, wheel.name)
    for name in NATIVE:
        if (site / (name + ".libs")).exists():
            raise RuntimeError(
                f"Opaque native wheel bundle survived replacement: {name}"
            )
    native = {
        d.metadata["Name"].lower(): d.version
        for d in distributions(path=[str(site)])
        if d.metadata["Name"].lower() in NATIVE
    }
    if set(native) != NATIVE:
        raise RuntimeError(f"Missing native distribution metadata: {native}")
    print(json.dumps(native, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("install", type=Path)
    parser.add_argument("wheels", type=Path)
    args = parser.parse_args()
    replace(args.install, args.wheels)
