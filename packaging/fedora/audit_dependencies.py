"""Query official Fedora repositories; exit 2 for missing/incompatible providers.

This is a prerequisite inventory, not a complete solver or proof of acceptance.
DNF/network errors remain fatal and cannot be mistaken for missing packages.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import InvalidVersion, Version

# Upstream metadata baseline: faster-whisper 1.2.1, CustomTkinter 5.2.2.
# Recheck this inventory when upgrading either dependency. The real RPM build
# also resolves generated BuildRequires and the entire native dependency chain.
TRANSITIVE = [
    "ctranslate2>=4,<5",
    "huggingface-hub>=0.21",
    "tokenizers>=0.13,<1",
    "onnxruntime>=1.14,<2",
    "tqdm",
    "darkdetect",
    "numpy",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path("pyproject.toml"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project = tomllib.loads(args.project.read_text(encoding="utf-8"))["project"]
    rows = []
    for scope, entries in [
        ("direct", project["dependencies"]),
        ("transitive-baseline", TRANSITIVE),
    ]:
        for entry in entries:
            req = Requirement(entry)
            if req.marker and not req.marker.evaluate():
                continue
            capability = f"python3dist({req.name.lower().replace('_', '-')})"
            command = [
                "dnf",
                "-q",
                "--repo=fedora",
                "--repo=updates",
                "repoquery",
                "--available",
                "--arch=noarch," + platform.machine(),
                "--latest-limit=1",
                "--qf=%{name}|%{version}|%{release}|%{arch}|%{repoid}\n",
                "--whatprovides",
                capability,
            ]
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            providers = []
            for line in result.stdout.splitlines():
                name, version, release, arch, repo = line.split("|")
                try:
                    compatible = Version(version) in req.specifier
                except InvalidVersion:
                    compatible = False
                providers.append(
                    dict(
                        name=name,
                        version=version,
                        release=release,
                        arch=arch,
                        repository=repo,
                        compatible=compatible,
                    )
                )
            status = (
                "available"
                if any(p["compatible"] for p in providers)
                else "incompatible"
                if providers
                else "missing"
            )
            rows.append(
                dict(
                    requirement=entry,
                    scope=scope,
                    capability=capability,
                    status=status,
                    providers=providers,
                )
            )
            print(f"{status:12} {entry}", flush=True)
    release = Path("/etc/os-release").read_text(encoding="utf-8")
    report = dict(
        checked_at=datetime.now(timezone.utc).isoformat(),
        os_release=release,
        repositories=["fedora", "updates"],
        architecture=platform.machine(),
        requirements=rows,
        prerequisites_available=all(r["status"] == "available" for r in rows),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["prerequisites_available"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
