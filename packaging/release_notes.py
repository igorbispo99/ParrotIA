"""Generate download-first GitHub release notes for exactly one version."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from parrotia import __version__  # noqa: E402

REPOSITORY = "https://github.com/igorbispo99/ParrotIA"
STORE_URL = "https://apps.microsoft.com/detail/9NXSSCQKW2XR"


def version_changes(changelog: str, version: str) -> str:
    """Extract one section, failing rather than falling back to all history."""
    headers = list(re.finditer(r"^## \[([^\]]+)\].*$", changelog, re.MULTILINE))
    for index, header in enumerate(headers):
        if header.group(1) == version:
            end = (
                headers[index + 1].start()
                if index + 1 < len(headers)
                else len(changelog)
            )
            section = changelog[header.end() : end]
            section = re.split(
                r"^\[[^\]]+\]:", section, maxsplit=1, flags=re.MULTILINE
            )[0]
            if section.strip():
                return section.strip()
    raise ValueError(f"No changelog entry for version {version}")


def render_release_notes(changelog: str, tag: str, assets: list[str]) -> str:
    if not re.fullmatch(r"v?\d+\.\d+\.\d+", tag):
        raise ValueError("Expected a version tag such as v1.5.2")
    version = tag.removeprefix("v")
    tag = f"v{version}"
    rows = []
    labels = [
        ("macOS · Apple Silicon", lambda n: n.endswith("-macos-arm64.dmg")),
        ("macOS · Intel", lambda n: n.endswith("-macos-x86_64.dmg")),
        ("Windows · x64 installer (not code-signed)", lambda n: n.endswith(".exe")),
        ("Linux · Debian / Ubuntu · x86-64", lambda n: n.endswith("_amd64.deb")),
        ("Linux · Debian / Ubuntu · ARM64", lambda n: n.endswith("_arm64.deb")),
        ("Linux · Fedora / RPM · x86-64", lambda n: n.endswith(".x86_64.rpm")),
        ("Linux · Fedora / RPM · ARM64", lambda n: n.endswith(".aarch64.rpm")),
        ("Python package", lambda n: n.endswith(".whl")),
        ("Source archive", lambda n: n.endswith(".tar.gz")),
    ]
    for label, matches in labels:
        if label.startswith("Windows") and any(matches(n) for n in assets):
            # The Store edition is signed by Microsoft; the setup program is not.
            rows.append(
                f"| Windows · Microsoft Store (recommended) | [Get it]({STORE_URL}) |"
            )
        for name in sorted(assets):
            if matches(name):
                url = f"{REPOSITORY}/releases/download/{tag}/{quote(name, safe='')}"
                rows.append(f"| {label} | [Download]({url}) |")
    if not rows:
        raise ValueError("No downloadable release artifacts found")
    changes = version_changes(changelog, version)
    return (
        "## Downloads\n\n| Platform | Installer / package |\n| --- | --- |\n"
        + "\n".join(rows)
        + "\n\n## What's changed\n\n"
        + changes
        + f"\n\n[Installation instructions]({REPOSITORY}/blob/main/README.md#installation)"
        + f" · [Full changelog]({REPOSITORY}/blob/{tag}/CHANGELOG.md)\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default=f"v{__version__}")
    parser.add_argument("--artifacts", type=Path, default=ROOT / "dist")
    parser.add_argument("--output", type=Path, default=ROOT / "build/release-notes.md")
    args = parser.parse_args()
    body = render_release_notes(
        (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
        args.tag,
        [path.name for path in args.artifacts.iterdir() if path.is_file()],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(body, encoding="utf-8")
    print(f"Generated {args.output} for {args.tag}")


if __name__ == "__main__":
    main()
