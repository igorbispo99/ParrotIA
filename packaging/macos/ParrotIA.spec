"""Native macOS app; build through packaging/macos/build.py."""
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata

root = Path(SPECPATH).resolve().parents[1]
import sys
sys.path.insert(0, str(root / "src"))
from parrotia import __version__

datas = [(str(root / "src/parrotia/assets"), "parrotia/assets")]
binaries = []
hiddenimports = ["_pywhispercpp", "PIL._tkinter_finder", "PIL._imagingtk"]
for package in ("customtkinter", "pywhispercpp", "av", "certifi"):
    package_data, package_binaries, package_imports = collect_all(package)
    datas += package_data
    binaries += package_binaries
    hiddenimports += package_imports
datas += copy_metadata("pywhispercpp")

a = Analysis(
    [str(root / "packaging/launcher.py")],
    pathex=[str(root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["faster_whisper", "ctranslate2", "onnxruntime", "torch", "tensorflow", "matplotlib", "pytest"],
)
pyz = PYZ(a.pure)
# BUNDLE inherits its signing settings from COLLECT, so the identity must reach
# COLLECT as well as EXE; otherwise only the launcher is signed and notarization
# rejects every bundled library.
sign_identity = os.environ.get("PARROTIA_SIGN_IDENTITY") or None
entitlements = (
    str(root / "packaging/macos/entitlements.plist") if sign_identity else None
)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="parrotia-gui", console=False, strip=False, upx=False,
    codesign_identity=sign_identity,
    entitlements_file=entitlements,
)
coll = COLLECT(
    exe, a.binaries, a.datas, strip=False, upx=False, name="ParrotIA",
    codesign_identity=sign_identity,
    entitlements_file=entitlements,
)
app = BUNDLE(
    coll,
    name="ParrotIA.app",
    icon=str(root / "build/macos/ParrotIA.icns"),
    bundle_identifier="io.github.igorbispo99.ParrotIA",
    version=__version__,
    info_plist={
        "CFBundleDisplayName": "ParrotIA",
        "CFBundleShortVersionString": __version__,
        "LSMinimumSystemVersion": "14.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "LSApplicationCategoryType": "public.app-category.productivity",
    },
)
