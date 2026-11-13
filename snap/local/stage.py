"""Stage Snap-only launchers, source and a license inventory after pip installs."""

from __future__ import annotations

import ast
import json
import shutil
import sys
import tarfile
from importlib.metadata import distributions
from pathlib import Path


def version(source: Path) -> str:
    tree = ast.parse((source / "src/parrotia/__init__.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if isinstance(value, str):
                return value
    raise ValueError("No literal __version__ found")


def inventory(install: Path, supplemental: Path = None) -> list:
    records = []
    sites = sorted(install.glob("lib/python*/site-packages"))
    for site in sites:
        for dist in sorted(
            distributions(path=[str(site)]), key=lambda d: d.metadata["Name"].lower()
        ):
            name = dist.metadata["Name"]
            copied = []
            for item in dist.files or []:
                # Keep original paths, including nested licenses for native wheels.
                if not any(
                    marker in item.name.lower()
                    for marker in ("license", "licence", "copyright", "notice")
                ):
                    continue
                origin = Path(dist.locate_file(item)).resolve()
                if not origin.is_file() or not origin.is_relative_to(install.resolve()):
                    continue
                relative = origin.relative_to(install.resolve())
                target = install / "share/licenses/parrotia/python" / name / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(origin, target)
                copied.append(str(target.relative_to(install)))
            if not copied and supplemental is not None:
                fallback = supplemental / (
                    name.lower().replace("_", "-") + "-LICENSE.txt"
                )
                if fallback.is_file():
                    target = (
                        install
                        / "share/licenses/parrotia/python"
                        / name
                        / fallback.name
                    )
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(fallback, target)
                    copied.append(str(target.relative_to(install)))
            records.append(
                {
                    "name": name,
                    "version": dist.version,
                    "license_expression": dist.metadata.get("License-Expression"),
                    "license": dist.metadata.get("License"),
                    "project_urls": dist.metadata.get_all("Project-URL", []),
                    "notices": copied,
                }
            )
    if not records:
        raise RuntimeError("No installed Python distributions found")
    return records


def stage(source: Path, install: Path) -> None:
    resources = install / "share/parrotia"
    resources.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "packaging/launcher.py", resources / "launcher.py")
    shutil.copy2(source / "snap/local/check.py", resources / "check.py")
    launcher = install / "bin/parrotia-env"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "snap/local/command-chain", launcher)
    launcher.chmod(0o755)
    desktop = install / "usr/share/applications/parrotia.desktop"
    desktop.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "snap/gui/parrotia.desktop", desktop)
    docs = install / "share/doc/parrotia"
    docs.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "LICENSE", docs / "LICENSE")
    shutil.copy2(source / "snap/README.md", docs / "SNAP-README.md")
    shutil.copy2(source / "snap/licenses/SOURCES.md", docs / "LICENSE-SOURCES.md")
    records = inventory(install, source / "snap/licenses")
    (docs / "python-dependencies.json").write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8"
    )
    # Include the actual application and Snap build sources without local media,
    # credentials, build output or unrelated platform work.
    selected = [
        "src/parrotia",
        "snap",
        "tests",
        "packaging/launcher.py",
        "pyproject.toml",
        "MANIFEST.in",
        "LICENSE",
        "README.md",
        "CHANGELOG.md",
        "requirements.txt",
    ]
    with tarfile.open(docs / "parrotia-source.tar.gz", "w:gz") as archive:
        for name in selected:
            path = source / name
            paths = sorted(path.rglob("*")) if path.is_dir() else [path]
            for entry in paths:
                if (
                    entry.is_file()
                    and "__pycache__" not in entry.parts
                    and entry.suffix != ".pyc"
                ):
                    archive.add(
                        entry, arcname=str(entry.relative_to(source)), recursive=False
                    )
    missing = [r["name"] for r in records if not r["notices"]]
    if missing:
        raise RuntimeError("Missing distribution license texts: " + ", ".join(missing))


if __name__ == "__main__":
    source = Path.cwd()
    if sys.argv[1:] == ["--version"]:
        print(version(source))
    elif len(sys.argv) == 2:
        stage(source, Path(sys.argv[1]))
    else:
        raise SystemExit("Usage: stage.py --version | INSTALL_DIRECTORY")
