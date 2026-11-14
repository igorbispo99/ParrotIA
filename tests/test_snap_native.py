"""Native packaging rejects corrupt or escaping upstream inputs before staging."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import sys
import tarfile
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "snap/local" / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


native = load("build_native")
replacement = load("replace_native")


@pytest.mark.skipif(
    sys.version_info < (3, 12), reason="core24 native builder uses Python 3.12"
)
def test_source_checksum_rejects_tampering(tmp_path):
    archive = tmp_path / "source.tar"
    archive.write_bytes(b"upstream source")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    native.verify(archive, digest)
    archive.write_bytes(b"tampered source")
    with pytest.raises(ValueError, match="checksum mismatch"):
        native.verify(archive, digest)


@pytest.mark.skipif(
    sys.version_info < (3, 12), reason="core24 extraction requires the data filter"
)
def test_source_archive_rejects_parent_traversal(tmp_path):
    archive = tmp_path / "source.tar"
    with tarfile.open(archive, "w") as output:
        member = tarfile.TarInfo("upstream/../../outside")
        member.size = 4
        output.addfile(member, io.BytesIO(b"evil"))
    with pytest.raises(ValueError, match="Unsafe archive"):
        native.extract(archive, tmp_path / "source")
    assert not (tmp_path / "outside").exists()


@pytest.mark.skipif(
    sys.version_info < (3, 12), reason="core24 extraction requires the data filter"
)
def test_source_archive_rejects_escaping_symlinks(tmp_path):
    archive = tmp_path / "source.tar"
    with tarfile.open(archive, "w") as output:
        member = tarfile.TarInfo("upstream/link")
        member.type = tarfile.SYMTYPE
        member.linkname = "../../outside"
        output.addfile(member)
    with pytest.raises(tarfile.FilterError):
        native.extract(archive, tmp_path / "source")


def test_installed_record_cannot_delete_outside_part(tmp_path):
    install = tmp_path / "install"
    install.mkdir()
    owned = install / "owned"
    owned.write_text("keep until all paths pass validation")
    outside = tmp_path / "outside"
    outside.write_text("private")
    dist = SimpleNamespace(
        files=["owned", "../outside"], locate_file=lambda p: install / p
    )
    with pytest.raises(ValueError, match="Unsafe installed RECORD"):
        replacement.uninstall(dist, install)
    assert owned.exists()
    assert outside.read_text() == "private"


def test_native_wheel_rejects_traversal_before_writing(tmp_path):
    wheel = tmp_path / "native.whl"
    with zipfile.ZipFile(wheel, "w") as output:
        output.writestr("av/okay.py", "")
        output.writestr("../outside", "evil")
    with pytest.raises(ValueError, match="Unsupported native wheel"):
        replacement.install_wheel(wheel, tmp_path / "site")
    assert not (tmp_path / "outside").exists()
    assert not (tmp_path / "site/av/okay.py").exists()


def test_replacement_removes_bootstrap_bundles_and_installs_built_runtime(tmp_path):
    install = tmp_path / "install"
    site = install / "lib/python3.12/site-packages"
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    for name in ["av", "numpy", "ctranslate2"]:
        metadata = site / (name + "-1.dist-info")
        metadata.mkdir(parents=True)
        (metadata / "METADATA").write_text(f"Name: {name}\nVersion: 1\n")
        bundle = site / (name + ".libs")
        bundle.mkdir()
        (bundle / "opaque.so").write_bytes(b"old wheel")
        (metadata / "RECORD").write_text(
            f"{name}-1.dist-info/METADATA,,\n{name}-1.dist-info/RECORD,,\n{name}.libs/opaque.so,,\n"
        )
        with zipfile.ZipFile(wheels / (name + "-1-built.whl"), "w") as output:
            output.writestr(name + "/__init__.py", "# built runtime")
            output.writestr(
                name + "-1.dist-info/METADATA", f"Name: {name}\nVersion: 1\n"
            )
            output.writestr(name + "-1.dist-info/RECORD", "")
    replacement.replace(install, wheels)
    for name in ["av", "numpy", "ctranslate2"]:
        assert not (site / (name + ".libs")).exists()
        assert (site / name / "__init__.py").read_text() == "# built runtime"
