"""Exercise Snap staging and the shared command chain without downloading models."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "snap_stage", ROOT / "snap/local/stage.py"
)
snap_stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(snap_stage)


def test_version_does_not_import_application(tmp_path):
    source = tmp_path / "src/parrotia"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text(
        '__version__ = "9.8.7"\nraise RuntimeError("must not import")\n'
    )
    assert snap_stage.version(tmp_path) == "9.8.7"


def test_inventory_preserves_nested_notices_and_rejects_outside_files(tmp_path):
    install = tmp_path / "install"
    site = install / "lib/python3.12/site-packages"
    metadata = site / "example-1.0.dist-info"
    metadata.mkdir(parents=True)
    (metadata / "METADATA").write_text(
        "Metadata-Version: 2.4\nName: example\nVersion: 1.0\nLicense-Expression: MIT\n"
    )
    notice = metadata / "licenses/native/NOTICE"
    notice.parent.mkdir(parents=True)
    notice.write_text("native notice")
    outside = tmp_path / "LICENSE-private"
    outside.write_text("must not copy")
    (metadata / "RECORD").write_text(
        "example-1.0.dist-info/licenses/native/NOTICE,,\n"
        "../../../../LICENSE-private,,\n"
    )
    result = snap_stage.inventory(install)
    assert result[0]["license_expression"] == "MIT"
    assert len(result[0]["notices"]) == 1
    assert (install / result[0]["notices"][0]).read_text() == "native notice"
    assert outside.read_text() == "must not copy"


def test_inventory_uses_versioned_supplemental_text(tmp_path):
    install = tmp_path / "install"
    metadata = install / "lib/python3.12/site-packages/tokenizers-1.dist-info"
    metadata.mkdir(parents=True)
    (metadata / "METADATA").write_text("Name: tokenizers\nVersion: 1\n")
    supplemental = tmp_path / "supplemental"
    supplemental.mkdir()
    (supplemental / "tokenizers-LICENSE.txt").write_text("upstream Apache text")
    records = snap_stage.inventory(install, supplemental)
    assert len(records[0]["notices"]) == 1
    assert (install / records[0]["notices"][0]).read_text() == "upstream Apache text"


def test_staging_includes_source_and_inventory_without_workspace_secrets(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for name in ("src/parrotia", "snap", "packaging"):
        shutil.copytree(
            ROOT / name, source / name, ignore=shutil.ignore_patterns("__pycache__")
        )
    for name in (
        "pyproject.toml",
        "MANIFEST.in",
        "LICENSE",
        "README.md",
        "CHANGELOG.md",
        "requirements.txt",
    ):
        shutil.copy2(ROOT / name, source / name)
    (source / ".env").write_text("PRIVATE=secret")
    install = tmp_path / "install"
    metadata = install / "lib/python3.12/site-packages/demo-1.dist-info"
    metadata.mkdir(parents=True)
    (metadata / "METADATA").write_text("Name: demo\nVersion: 1\n")
    (metadata / "LICENSE").write_text("test license")
    (metadata / "RECORD").write_text("demo-1.dist-info/LICENSE,,\n")
    snap_stage.stage(source, install)
    records = json.loads(
        (install / "share/doc/parrotia/python-dependencies.json").read_text()
    )
    assert records[0]["name"] == "demo"
    with tarfile.open(install / "share/doc/parrotia/parrotia-source.tar.gz") as archive:
        names = archive.getnames()
    assert "snap/snapcraft.yaml" in names
    assert "src/parrotia/transcriber.py" in names
    assert ".env" not in names
    assert not any("__pycache__" in name for name in names)
    if os.name != "nt":
        assert (install / "bin/parrotia-env").stat().st_mode & 0o111


@pytest.mark.skipif(os.name == "nt", reason="Run POSIX launcher checks on Linux")
def test_launcher_uses_persistent_cache_and_preserves_arguments(tmp_path):
    common = tmp_path / "common with spaces"
    env = dict(os.environ, SNAP=str(tmp_path / "snap"), SNAP_USER_COMMON=str(common))
    result = subprocess.run(
        [
            "sh",
            str(ROOT / "snap/local/command-chain"),
            "/bin/sh",
            "-c",
            'printf "%s\\n" "$HF_HUB_CACHE" "$HF_HUB_DISABLE_TELEMETRY" "$PYTHONNOUSERSITE" "$1"',
            "check",
            "audio with spaces.wav",
        ],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout.splitlines() == [
        str(common / "huggingface/hub"),
        "1",
        "1",
        "audio with spaces.wav",
    ]
    assert (common / "huggingface/hub").is_dir()
