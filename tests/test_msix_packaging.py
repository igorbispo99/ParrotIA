"""The Store package must carry a valid identity, full-trust launch and real logos."""

import runpy
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
msix = runpy.run_path(str(ROOT / "packaging/windows/msix.py"))
NS = {
    "p": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
    "uap": "http://schemas.microsoft.com/appx/manifest/uap/windows10",
    "rescap": "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities",
}
IDENTITY = ("IgorBispo.ParrotIA", "CN=11111111-2222-3333-4444-555555555555", "Igor Bispo")


def manifest(*identity, version="1.5.3"):
    return ET.fromstring(msix["render_manifest"](*(identity or IDENTITY), version))


def test_version_has_four_parts_with_store_reserved_revision():
    assert msix["msix_version"]("1.5.3") == "1.5.3.0"
    for bad in ("1.5", "1.5.3.1", "1.5.x", "70000.1.1"):
        with pytest.raises(ValueError):
            msix["msix_version"](bad)


def test_manifest_declares_identity_and_full_trust_launch():
    root = manifest()
    identity = root.find("p:Identity", NS)
    assert identity.attrib["Name"] == "IgorBispo.ParrotIA"
    assert identity.attrib["Publisher"] == "CN=11111111-2222-3333-4444-555555555555"
    assert identity.attrib["Version"] == "1.5.3.0"
    assert identity.attrib["ProcessorArchitecture"] == "x64"
    app = root.find("p:Applications/p:Application", NS)
    assert app.attrib["Executable"] == "parrotia-gui.exe"
    assert app.attrib["EntryPoint"] == "Windows.FullTrustApplication"
    capability = root.find("p:Capabilities/rescap:Capability", NS)
    assert capability.attrib["Name"] == "runFullTrust"
    # No other capability is requested: the app needs no more than full trust.
    assert len(root.findall("p:Capabilities/*", NS)) == 1


def test_manifest_escapes_publisher_display_name():
    root = manifest(IDENTITY[0], IDENTITY[1], "Igor & <Co>")
    assert root.find("p:Properties/p:PublisherDisplayName", NS).text == "Igor & <Co>"


@pytest.mark.parametrize(
    "identity",
    [
        ("ab", IDENTITY[1], IDENTITY[2]),  # too short
        ("Bad Name", IDENTITY[1], IDENTITY[2]),  # space
        (IDENTITY[0], "11111111-2222", IDENTITY[2]),  # not a CN= subject
        (IDENTITY[0], IDENTITY[1], "  "),  # empty display name
    ],
)
def test_invalid_identity_is_rejected(identity):
    with pytest.raises(ValueError):
        msix["render_manifest"](*identity, "1.5.3")


def test_every_logo_in_the_manifest_is_generated_at_its_size(tmp_path):
    from PIL import Image

    msix["make_logos"](tmp_path / "Assets")
    root = manifest()
    visual = root.find("p:Applications/p:Application/uap:VisualElements", NS)
    referenced = {
        root.find("p:Properties/p:Logo", NS).text,
        visual.attrib["Square150x150Logo"],
        visual.attrib["Square44x44Logo"],
    }
    assert referenced == {rf"Assets\{name}" for name in msix["LOGOS"]}
    for name, size in msix["LOGOS"].items():
        with Image.open(tmp_path / "Assets" / name) as logo:
            assert logo.size == size


def run_main(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["msix.py", *args])
    msix["main"]()


def test_store_build_refuses_placeholder_or_partial_identity(monkeypatch):
    for args in ([], ["--identity-name", "IgorBispo.ParrotIA"]):
        with pytest.raises(SystemExit) as stopped:
            run_main(monkeypatch, *args)
        assert stopped.value.code == 2


def test_test_package_cannot_be_mixed_with_real_identity(monkeypatch):
    with pytest.raises(SystemExit) as stopped:
        run_main(monkeypatch, "--test-package", "--identity-name", "IgorBispo.ParrotIA")
    assert stopped.value.code == 2


def test_layout_contains_app_manifest_and_logos(monkeypatch, tmp_path):
    bundle = tmp_path / "bundle"
    (bundle / "_internal").mkdir(parents=True)
    (bundle / "parrotia-gui.exe").write_bytes(b"MZ")
    (bundle / "_internal/lib.dll").write_bytes(b"x")
    layout = tmp_path / "layout"
    run_main(
        monkeypatch, "--test-package", "--layout-only",
        "--bundle", str(bundle), "--layout-dir", str(layout),
    )
    assert (layout / "parrotia-gui.exe").is_file()
    assert (layout / "_internal/lib.dll").is_file()
    assert (layout / "Assets/StoreLogo.png").is_file()
    identity = ET.parse(layout / "AppxManifest.xml").getroot().find("p:Identity", NS)
    assert identity.attrib["Name"] == "IgorBispo.ParrotIA.Test"


def test_missing_bundle_stops_with_instructions(monkeypatch, tmp_path):
    with pytest.raises(SystemExit, match="--bundle-only"):
        run_main(
            monkeypatch, "--test-package", "--layout-only",
            "--bundle", str(tmp_path), "--layout-dir", str(tmp_path / "layout"),
        )
