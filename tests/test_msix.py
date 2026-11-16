"""Microsoft Store (MSIX) runtime behavior and package generation.

Nothing here installs a package or calls the Windows SDK; see
packaging/windows/test-msix.ps1 for the installed-package check.
"""

from __future__ import annotations

import ctypes
import importlib.util
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import pytest

from parrotia import SUPPORTED_EXTENSIONS, _msix

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "msix_build", ROOT / "packaging/windows/msix.py"
)
msix_build = importlib.util.module_from_spec(SPEC)
# Dataclasses look their module up in sys.modules while being defined.
sys.modules[SPEC.name] = msix_build
SPEC.loader.exec_module(msix_build)

NS = {
    "m": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
    "uap": "http://schemas.microsoft.com/appx/manifest/uap/windows10",
    "uap3": "http://schemas.microsoft.com/appx/manifest/uap/windows10/3",
    "desktop": "http://schemas.microsoft.com/appx/manifest/desktop/windows10",
    "rescap": "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities",
}


# ---------------------------------------------------------------- runtime ---


FAMILY = "12345IgorBispo.ParrotIA_abcdef0123456"
LOCAL = r"C:\Users\me\AppData\Local"


class _FakePackageApi:
    """Mimics GetCurrentPackageFamilyName's two-call buffer protocol."""

    def __init__(self, family) -> None:
        self.family = family
        self.argtypes = self.restype = None

    def __call__(self, length, buffer) -> int:
        if self.family is None:
            return 15700  # APPMODEL_ERROR_NO_PACKAGE
        if buffer is None:
            length._obj.value = len(self.family) + 1
            return 122  # ERROR_INSUFFICIENT_BUFFER
        buffer.value = self.family
        return 0


@pytest.mark.parametrize("family", [FAMILY, None])
def test_package_identity_from_windows_api(monkeypatch, family):
    pytest.importorskip("ctypes.wintypes")
    api = SimpleNamespace(
        kernel32=SimpleNamespace(GetCurrentPackageFamilyName=_FakePackageApi(family))
    )
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(ctypes, "windll", api, raising=False)
    assert _msix.package_family_name() == family
    assert _msix.is_packaged() is (family is not None)


def test_is_packaged_false_off_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert _msix.is_packaged() is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows API")
def test_test_process_is_not_packaged():
    assert _msix.package_family_name() is None


def test_packaged_cache_is_in_package_local_cache():
    # Not plain %LOCALAPPDATA%: Windows won't redirect writes into a folder the
    # Inno Setup build already created there, so uninstall would leave models.
    assert _msix.packaged_model_cache(FAMILY, {"LOCALAPPDATA": LOCAL}) == Path(
        LOCAL, "Packages", FAMILY, "LocalCache", "huggingface"
    )


@pytest.mark.parametrize("variable", ["HF_HOME", "HF_HUB_CACHE"])
def test_packaged_cache_respects_explicit_configuration(variable):
    environ = {"LOCALAPPDATA": LOCAL, variable: r"D:\models"}
    assert _msix.packaged_model_cache(FAMILY, environ) is None


def test_packaged_cache_needs_identity_and_local_appdata():
    assert _msix.packaged_model_cache(None, {"LOCALAPPDATA": LOCAL}) is None
    assert _msix.packaged_model_cache(FAMILY, {}) is None


def test_configure_sets_cache_only_when_packaged(monkeypatch):
    monkeypatch.setattr(_msix, "package_family_name", lambda: FAMILY)
    packaged = {"LOCALAPPDATA": LOCAL}
    assert _msix.configure_packaged_environment(packaged) is True
    assert packaged["HF_HOME"] == str(
        Path(LOCAL, "Packages", FAMILY, "LocalCache", "huggingface")
    )

    monkeypatch.setattr(_msix, "package_family_name", lambda: None)
    unpackaged = {"LOCALAPPDATA": LOCAL}
    assert _msix.configure_packaged_environment(unpackaged) is False
    assert "HF_HOME" not in unpackaged


def test_configure_keeps_user_cache(monkeypatch):
    monkeypatch.setattr(_msix, "package_family_name", lambda: FAMILY)
    environ = {"LOCALAPPDATA": LOCAL, "HF_HOME": r"D:\hf"}
    assert _msix.configure_packaged_environment(environ) is True
    assert environ["HF_HOME"] == r"D:\hf"


def test_local_data_dir_separates_store_and_installer_builds(monkeypatch):
    environ = {"LOCALAPPDATA": LOCAL}
    monkeypatch.setattr(_msix, "package_family_name", lambda: None)
    assert _msix.local_data_dir(environ) == Path(LOCAL, "ParrotIA")
    monkeypatch.setattr(_msix, "package_family_name", lambda: FAMILY)
    assert _msix.local_data_dir(environ) == Path(
        LOCAL, "Packages", FAMILY, "LocalCache"
    )


def test_importing_parrotia_leaves_hugging_face_unloaded():
    """HF_HOME only takes effect if set before huggingface_hub is imported."""
    import subprocess

    code = (
        "import sys, parrotia, parrotia._msix; "
        "sys.exit('huggingface_hub' in sys.modules)"
    )
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0


class _FakeApp:
    instances: list = []

    def __init__(self) -> None:
        self.inputs: list = []
        self.ran = False
        _FakeApp.instances.append(self)

    def set_input(self, path: str) -> None:
        self.inputs.append(path)

    def mainloop(self) -> None:
        self.ran = True


@pytest.mark.parametrize(
    "argv, expected",
    [
        ([r"C:\media\talk.mp3"], [r"C:\media\talk.mp3"]),
        (["--flag", r"C:\media\a.wav", r"C:\media\b.wav"], [r"C:\media\a.wav"]),
        ([], []),
    ],
)
def test_gui_preloads_open_with_path(monkeypatch, argv, expected):
    app_module = pytest.importorskip("parrotia.app")
    monkeypatch.setattr(app_module, "TranscriberApp", _FakeApp)
    _FakeApp.instances.clear()
    app_module.main(argv)
    (app,) = _FakeApp.instances
    assert app.inputs == expected
    assert app.ran


# ---------------------------------------------------------------- package ---


IDENTITY = msix_build.Identity(
    name="12345IgorBispo.ParrotIA",
    publisher="CN=01234567-89AB-CDEF-0123-456789ABCDEF",
    publisher_display_name="Bispo & Co <test>",
)


@pytest.mark.parametrize(
    "version, expected",
    [
        ("1.4.1", "1.4.1.0"),
        ("2.0", "2.0.0.0"),
        ("3", "3.0.0.0"),
        ("1.65535.0", "1.65535.0.0"),
    ],
)
def test_msix_version_reserves_fourth_field(version, expected):
    assert msix_build.msix_version(version) == expected


@pytest.mark.parametrize("version", ["0.9.0", "1.2.3.4", "1.4.1rc1", "1.70000.0", ""])
def test_msix_version_rejects_invalid(version):
    with pytest.raises(ValueError):
        msix_build.msix_version(version)


def _manifest(version: str = "1.4.1") -> ET.Element:
    return ET.fromstring(
        msix_build.render_manifest(IDENTITY, version, SUPPORTED_EXTENSIONS).encode()
    )


def test_manifest_identity_and_version():
    root = _manifest()
    identity = root.find("m:Identity", NS)
    assert identity.get("Name") == IDENTITY.name
    assert identity.get("Publisher") == IDENTITY.publisher
    assert identity.get("Version") == "1.4.1.0"
    assert identity.get("ProcessorArchitecture") == "x64"
    # Escaped in the XML, restored by the parser.
    assert root.findtext("m:Properties/m:PublisherDisplayName", namespaces=NS) == (
        IDENTITY.publisher_display_name
    )


def test_manifest_runs_frozen_app_with_full_trust():
    root = _manifest()
    (application,) = root.findall("m:Applications/m:Application", NS)
    assert application.get("Executable") == "parrotia-gui.exe"
    assert application.get("EntryPoint") == "Windows.FullTrustApplication"
    capability = root.find("m:Capabilities/rescap:Capability", NS)
    assert capability.get("Name") == "runFullTrust"
    family = root.find("m:Dependencies/m:TargetDeviceFamily", NS)
    assert family.get("Name") == "Windows.Desktop"
    assert family.get("MinVersion") == "10.0.17763.0"
    alias = root.find(".//desktop:ExecutionAlias", NS)
    assert alias.get("Alias") == "parrotia-app.exe"


def test_manifest_registers_every_media_type_and_explorer_verb():
    root = _manifest()
    association = root.find(".//uap3:FileTypeAssociation", NS)
    assert association.get("MultiSelectModel") == "Document"
    types = [t.text for t in association.findall(".//uap:FileType", NS)]
    assert sorted(types) == sorted({e.lower() for e in SUPPORTED_EXTENSIONS})
    (verb,) = association.findall(".//uap3:Verb", NS)
    assert verb.text == "Transcribe on Parrot"
    assert verb.get("Parameters") == '--shell "%1"'
    # One process receives the whole selection, like the Inno Setup verb.
    assert verb.get("MultiSelectModel") == "Player"


def test_manifest_rejects_bad_extensions():
    with pytest.raises(ValueError):
        msix_build.render_manifest(IDENTITY, "1.0.0", [".mp3", "wav"])
    with pytest.raises(ValueError):
        msix_build.render_manifest(IDENTITY, "1.0.0", [])


def test_checked_in_identity_loads(tmp_path):
    identity = msix_build.load_identity()
    assert identity.publisher.startswith("CN=")
    bad = tmp_path / "identity.json"
    bad.write_text(
        '{"name": "has space", "publisher": "CN=x", "publisher_display_name": "x"}'
    )
    with pytest.raises(ValueError):
        msix_build.load_identity(bad)
    bad.write_text(
        '{"name": "Good.Name", "publisher": "Igor", "publisher_display_name": "x"}'
    )
    with pytest.raises(ValueError):
        msix_build.load_identity(bad)


def test_assets_cover_every_manifest_logo(tmp_path):
    from PIL import Image

    written = {p.name: p for p in msix_build.write_assets(tmp_path)}
    for name, width, height, _ in msix_build.ASSETS:
        with Image.open(written[name]) as image:
            assert image.size == (width, height)
            assert image.mode == "RGBA"
    manifest = msix_build.render_manifest(IDENTITY, "1.0.0", SUPPORTED_EXTENSIONS)
    logos = set(re.findall(r"Assets\\(\w+)\.png", manifest))
    assert logos == {
        "StoreLogo",
        "Square150x150Logo",
        "Square44x44Logo",
        "Wide310x150Logo",
    }
    for logo in logos:
        assert f"{logo}.scale-100.png" in written
    # The taskbar and Start use unplated target sizes for crisp small icons.
    for size in (16, 24, 32, 48, 256):
        assert f"Square44x44Logo.targetsize-{size}_altform-unplated.png" in written


def test_store_icon_is_300_square(tmp_path):
    from PIL import Image

    path = msix_build.write_store_icon(tmp_path / "icon.png")
    with Image.open(path) as image:
        assert image.size == (300, 300)
