"""Package the frozen Windows app as MSIX for Microsoft Store submission.

Run `python packaging/windows/build.py --bundle-only` first. The Store re-signs
the submitted package, so no code signing certificate is needed for it. The
package identity (name and publisher) is assigned by Partner Center when the
product name is reserved; pass those values with the options below or the
MSIX_IDENTITY_NAME, MSIX_PUBLISHER and MSIX_PUBLISHER_DISPLAY_NAME variables.
`--test-package` uses placeholder values for CI and local sideload tests only.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from parrotia import __version__  # noqa: E402

TEST_IDENTITY = ("IgorBispo.ParrotIA.Test", "CN=ParrotIA Test", "ParrotIA (test build)")
APPLICATION_ID = "ParrotIA"
EXECUTABLE = "parrotia-gui.exe"
DESCRIPTION = "Transcribe audio and video privately on your PC with Whisper."
# Pixel size of each logo referenced by the manifest.
LOGOS = {
    "StoreLogo.png": (50, 50),
    "Square44x44Logo.png": (44, 44),
    "Square150x150Logo.png": (150, 150),
}


def msix_version(version: str) -> str:
    """Return a four-part MSIX version; the Store reserves the last part (0)."""
    parts = version.split(".")
    if len(parts) != 3 or not all(
        part.isdigit() and int(part) <= 65535 for part in parts
    ):
        raise ValueError(f"Expected a version like 1.5.3, got {version!r}")
    return ".".join([*parts, "0"])


def validate_identity(name: str, publisher: str, display_name: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][-.A-Za-z0-9]{2,49}", name):
        raise ValueError(
            "Identity name must be 3-50 letters, digits, dots or hyphens "
            f"(copy it from Partner Center), got {name!r}"
        )
    if not publisher.startswith("CN="):
        raise ValueError(
            f"Publisher must be the Partner Center subject starting 'CN=', got {publisher!r}"
        )
    if not display_name.strip():
        raise ValueError("Publisher display name must not be empty")


def render_manifest(name: str, publisher: str, display_name: str, version: str) -> str:
    """Render AppxManifest.xml for a full-trust desktop app."""
    validate_identity(name, publisher, display_name)
    q = quoteattr
    return f"""<?xml version="1.0" encoding="utf-8"?>
<Package
  xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
  xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
  xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
  IgnorableNamespaces="uap rescap">
  <Identity Name={q(name)} Publisher={q(publisher)} Version={q(msix_version(version))} ProcessorArchitecture="x64" />
  <Properties>
    <DisplayName>ParrotIA</DisplayName>
    <PublisherDisplayName>{escape(display_name)}</PublisherDisplayName>
    <Logo>Assets\\StoreLogo.png</Logo>
  </Properties>
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.17763.0" MaxVersionTested="10.0.22621.0" />
  </Dependencies>
  <Resources>
    <Resource Language="en-us" />
  </Resources>
  <Applications>
    <Application Id="{APPLICATION_ID}" Executable="{EXECUTABLE}" EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="ParrotIA" Description={q(DESCRIPTION)} BackgroundColor="transparent" Square150x150Logo="Assets\\Square150x150Logo.png" Square44x44Logo="Assets\\Square44x44Logo.png" />
    </Application>
  </Applications>
  <Capabilities>
    <rescap:Capability Name="runFullTrust" />
  </Capabilities>
</Package>
"""


def make_logos(assets: Path) -> None:
    """Scale the application icon to every logo size the manifest references."""
    from PIL import Image

    assets.mkdir(parents=True, exist_ok=True)
    with Image.open(ROOT / "src/parrotia/assets/parrotia.png") as source:
        icon = source.convert("RGBA")
        for filename, size in LOGOS.items():
            icon.resize(size, Image.Resampling.LANCZOS).save(assets / filename)


def build_layout(bundle: Path, layout: Path, manifest: str) -> None:
    if not (bundle / EXECUTABLE).is_file():
        raise SystemExit(
            f"{bundle / EXECUTABLE} not found; run build.py --bundle-only first."
        )
    if layout.exists():
        shutil.rmtree(layout)
    shutil.copytree(bundle, layout)
    (layout / "AppxManifest.xml").write_text(manifest, encoding="utf-8")
    make_logos(layout / "Assets")


def find_makeappx() -> str:
    found = shutil.which("makeappx.exe")
    if found:
        return found
    sdk = (
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
        / "Windows Kits/10/bin"
    )
    candidates = sorted(sdk.glob("*/x64/makeappx.exe"), reverse=True)
    if candidates:
        return str(candidates[0])
    raise SystemExit(
        "Install the Windows SDK or pass --makeappx <path-to-makeappx.exe>."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=ROOT / "dist/ParrotIA")
    parser.add_argument("--layout-dir", type=Path, default=ROOT / "build/msix/layout")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist/msix")
    parser.add_argument("--identity-name", default=os.environ.get("MSIX_IDENTITY_NAME"))
    parser.add_argument("--publisher", default=os.environ.get("MSIX_PUBLISHER"))
    parser.add_argument(
        "--publisher-display-name",
        default=os.environ.get("MSIX_PUBLISHER_DISPLAY_NAME"),
    )
    parser.add_argument(
        "--test-package",
        action="store_true",
        help="Use placeholder identity values; the result cannot be submitted.",
    )
    parser.add_argument("--layout-only", action="store_true", help="Skip makeappx.")
    parser.add_argument("--makeappx", help="Path to makeappx.exe.")
    args = parser.parse_args()

    supplied = (args.identity_name, args.publisher, args.publisher_display_name)
    if args.test_package:
        if any(supplied):
            parser.error("--test-package cannot be combined with identity values.")
        name, publisher, display_name = TEST_IDENTITY
    elif all(supplied):
        name, publisher, display_name = supplied
    else:
        parser.error(
            "Pass --identity-name, --publisher and --publisher-display-name from "
            "Partner Center (Product identity), or use --test-package."
        )
    try:
        manifest = render_manifest(name, publisher, display_name, __version__)
    except ValueError as error:
        parser.error(str(error))
    build_layout(args.bundle, args.layout_dir, manifest)
    print(f"Layout: {args.layout_dir}")
    if args.layout_only:
        return
    if sys.platform != "win32":
        parser.error(
            "Packing needs makeappx.exe; run on Windows or pass --layout-only."
        )
    suffix = "-test" if args.test_package else ""
    args.output_dir.mkdir(parents=True, exist_ok=True)
    package = args.output_dir / f"ParrotIA-{__version__}-windows-x64{suffix}.msix"
    subprocess.run(
        [
            args.makeappx or find_makeappx(),
            "pack",
            "/o",
            "/d",
            str(args.layout_dir),
            "/p",
            str(package),
        ],
        check=True,
    )
    print(f"Package: {package}")


if __name__ == "__main__":
    main()
