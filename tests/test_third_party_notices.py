"""The shipped notices must match the native libraries and carry a source offer."""

import json
import re
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "packaging/windows"
third_party = runpy.run_path(str(HERE / "third_party.py"))
DATA = json.loads((HERE / "native-components.json").read_text(encoding="utf-8"))


def test_every_component_pins_its_source_and_has_license_files():
    for c in DATA["components"]:
        assert c["source"].startswith("https://"), c["name"]
        assert re.fullmatch(r"[0-9a-f]{64}", c["sha256"]), c["name"]
        assert c["license_files"], c["name"]
        for filename in c["license_files"]:
            text = (HERE / "licenses" / c["directory"] / filename).read_text(
                encoding="utf-8"
            )
            assert len(text) > 500, f"{c['name']}/{filename} looks empty"


def test_no_dll_is_claimed_twice():
    names = [dll for c in DATA["components"] for dll in c["dlls"]]
    names += [e["dll"] for e in DATA["toolchain_runtime"]["libraries"]]
    assert len(names) == len(set(names))


def bundle_with(tmp_path, dlls):
    libs = tmp_path / "bundle/_internal/av.libs"
    libs.mkdir(parents=True)
    for name in dlls:
        (libs / f"{name}-0123456789abcdef0123456789abcdef.dll").write_bytes(b"MZ")
    return tmp_path / "bundle"


def test_complete_bundle_has_no_problems(tmp_path, monkeypatch):
    monkeypatch.setitem(
        third_party["check_native_libs"].__globals__,
        "metadata",
        _FakeMetadata(DATA["pyav_version"]),
    )
    bundle = bundle_with(tmp_path, third_party["native_dll_names"](DATA))
    assert third_party["check_native_libs"](bundle, DATA, strict=True) == []


def test_new_native_library_is_flagged_and_fatal_in_strict_mode(tmp_path, monkeypatch):
    monkeypatch.setitem(
        third_party["check_native_libs"].__globals__,
        "metadata",
        _FakeMetadata(DATA["pyav_version"]),
    )
    dlls = sorted(third_party["native_dll_names"](DATA)) + ["libnewcodec"]
    bundle = bundle_with(tmp_path, dlls)
    assert any(
        "libnewcodec" in p
        for p in third_party["check_native_libs"](bundle, DATA, strict=False)
    )
    with pytest.raises(SystemExit, match="native-components.json"):
        third_party["check_native_libs"](bundle, DATA, strict=True)


def test_other_pyav_version_is_flagged(tmp_path, monkeypatch):
    monkeypatch.setitem(
        third_party["check_native_libs"].__globals__,
        "metadata",
        _FakeMetadata("99.0.0"),
    )
    bundle = bundle_with(tmp_path, third_party["native_dll_names"](DATA))
    assert any(
        "99.0.0" in p
        for p in third_party["check_native_libs"](bundle, DATA, strict=False)
    )


class _FakeMetadata:
    PackageNotFoundError = Exception

    def __init__(self, av_version):
        self._version = av_version

    def version(self, name):
        return self._version


def test_rendered_notices_carry_offer_sources_and_license_texts():
    text = third_party["render_notices"](
        "1.5.3",
        [("example", "1.0", "MIT", [("LICENSE", "MIT License text for example")])],
        DATA,
        [("Python LICENSE.txt", "PSF license text")],
    )
    assert "OFFER OF CORRESPONDING SOURCE" in text
    assert "at least three years" in text
    assert "MIT License text for example" in text and "PSF license text" in text
    for c in DATA["components"]:
        assert c["sha256"] in text and c["source"] in text
    # Full GPL text for the encoders, not just a name.
    assert "GNU GENERAL PUBLIC LICENSE" in text
    assert "libx264-165" in text and "libx265" in text
    assert "Roboto" in text and "Silero" in text


def test_hash_suffix_is_stripped_from_wheel_dll_names():
    strip = third_party["HASH_SUFFIX"]
    assert strip.sub("", "libvpx-1-38819e9ecbcee0c29c32bf28cdb995b5") == "libvpx-1"
    assert strip.sub("", "zlib1-b707f9beca0a740c87bad98fe93d6b8a") == "zlib1"
