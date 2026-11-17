"""Release casks must bind each architecture to its exact installer bytes."""

import hashlib
import runpy
from pathlib import Path

import pytest

render_cask = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "packaging/macos/update_cask.py")
)["render_cask"]


def test_cask_pins_both_installer_checksums(tmp_path):
    for arch, payload in (("arm64", b"arm installer"), ("x86_64", b"intel installer")):
        (tmp_path / f"ParrotIA-1.5.1-macos-{arch}.dmg").write_bytes(payload)
    cask = render_cask("1.5.1", tmp_path)
    assert f'arm:   "{hashlib.sha256(b"arm installer").hexdigest()}"' in cask
    assert f'intel: "{hashlib.sha256(b"intel installer").hexdigest()}"' in cask
    assert 'version "1.5.1"' in cask
    assert "#{version}" in cask and "#{arch}" in cask
    assert ":no_check" not in cask


def test_cask_requires_both_architectures(tmp_path):
    (tmp_path / "ParrotIA-1.5.1-macos-arm64.dmg").write_bytes(b"arm installer")
    with pytest.raises(FileNotFoundError):
        render_cask("1.5.1", tmp_path)


def test_cask_rejects_invalid_versions(tmp_path):
    with pytest.raises(ValueError, match="stable version"):
        render_cask('1.5.1"', tmp_path)
