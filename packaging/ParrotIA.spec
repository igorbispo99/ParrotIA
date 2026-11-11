# Shared Windows/Linux standalone app. Invoke through the platform build script.
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, copy_metadata

root = Path(SPECPATH).resolve().parent
datas = [(str(root / "src/parrotia/assets"), "parrotia/assets")]
binaries = []
# Pillow loads its Tk bridge dynamically; its Linux finder is otherwise missed.
hiddenimports = ["PIL._tkinter_finder", "PIL._imagingtk"]
for package in ("customtkinter", "faster_whisper", "ctranslate2", "av", "onnxruntime", "tokenizers"):
    package_data, package_binaries, package_imports = collect_all(package)
    datas += package_data
    binaries += package_binaries
    hiddenimports += package_imports
datas += copy_metadata("huggingface-hub")

a = Analysis(
    [str(root / "packaging/launcher.py")],
    pathex=[str(root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    # These optional integrations are unnecessary for faster-whisper inference.
    excludes=["torch", "tensorflow", "matplotlib", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="parrotia-gui", debug=False, strip=False, upx=False,
    console=sys.platform != "win32",
    icon=str(root / "src/parrotia/assets/parrotia.ico") if sys.platform == "win32" else None,
    version=str(root / "build/windows/version-info.txt") if sys.platform == "win32" else None,
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False, name="ParrotIA",
)
