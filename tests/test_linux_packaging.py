"""Native Linux builds must label payloads with the correct package architecture."""

import runpy
from pathlib import Path
from unittest.mock import patch

import pytest

MODULE = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "packaging/linux/build.py")
)


@pytest.mark.parametrize(
    "machine,deb,rpm",
    [
        ("x86_64", "amd64", "x86_64"),
        ("AMD64", "amd64", "x86_64"),
        ("aarch64", "arm64", "aarch64"),
        ("arm64", "arm64", "aarch64"),
    ],
)
def test_native_package_metadata(tmp_path, machine, deb, rpm):
    assert MODULE["package_architectures"](machine) == (deb, rpm)
    stage = tmp_path / "stage"
    stage.mkdir()
    output = tmp_path / "out"
    output.mkdir()

    def package(command, **kwargs):
        if command[0] == "dpkg-deb":
            assert f"Architecture: {deb}\n" in (stage / "DEBIAN/control").read_text()
            assert command[-1].endswith(f"_{deb}.deb")
        else:
            spec = Path(command[-1]).read_text()
            assert f"BuildArch: {rpm}\n" in spec
            assert not (stage / "DEBIAN").exists()
            artifact = (
                tmp_path
                / "rpmbuild/RPMS"
                / rpm
                / f"parrotia-{MODULE['__version__']}-1.{rpm}.rpm"
            )
            artifact.parent.mkdir()
            artifact.write_bytes(b"package")

    with patch("subprocess.run", side_effect=package):
        MODULE["build_rpm"](stage, output, tmp_path, rpm)
        MODULE["build_deb"](stage, output, deb)
    assert (output / f"parrotia-{MODULE['__version__']}-1.{rpm}.rpm").exists()


def test_unsupported_architecture():
    with pytest.raises(ValueError, match="Unsupported Linux architecture"):
        MODULE["package_architectures"]("armv7l")
