"""Build, smoke-test and package a native ParrotIA.app in a drag-install DMG."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from parrotia import __version__  # noqa: E402


def run(*args: str, **kwargs) -> None:
    subprocess.run(list(args), check=True, **kwargs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sign-identity", help="Developer ID Application identity in Keychain"
    )
    parser.add_argument(
        "--notary-profile", help="xcrun notarytool Keychain profile (requires signing)"
    )
    parser.add_argument(
        "--notary-keychain",
        help="Keychain file holding the notary profile (default: the user's keychains)",
    )
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Build on macOS using a native Python with Tk support.")
    if args.notary_profile and not args.sign_identity:
        parser.error("--notary-profile requires --sign-identity")
    if args.notary_keychain and not args.notary_profile:
        parser.error("--notary-keychain requires --notary-profile")
    arch = platform.machine()
    if arch not in ("arm64", "x86_64"):
        parser.error(f"Unsupported architecture: {arch}")

    generated = ROOT / "build/macos"
    generated.mkdir(parents=True, exist_ok=True)
    from PIL import Image

    with Image.open(ROOT / "src/parrotia/assets/parrotia.png") as icon:
        icon.convert("RGBA").resize((1024, 1024)).save(generated / "ParrotIA.icns")
    env = os.environ.copy()
    env["PYINSTALLER_CONFIG_DIR"] = str(generated / "pyinstaller-cache")
    # Inherited overrides must not change the backend of the packaged app test.
    env.pop("PARROTIA_BACKEND", None)
    if args.sign_identity:
        env["PARROTIA_SIGN_IDENTITY"] = args.sign_identity
        # A bundle that PyInstaller failed to sign must stop the build, not ship.
        env["PYINSTALLER_STRICT_BUNDLE_CODESIGN_ERROR"] = "1"
    else:
        env.pop("PARROTIA_SIGN_IDENTITY", None)
    run(
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        str(ROOT / "packaging/macos/ParrotIA.spec"),
        cwd=ROOT,
        env=env,
    )
    app = ROOT / "dist/ParrotIA.app"
    if args.sign_identity:
        # Every Mach-O file needs a valid Developer ID signature to be notarized.
        run("codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app))
    report = generated / "smoke-test.json"
    report.unlink(missing_ok=True)
    run(str(app / "Contents/MacOS/parrotia-gui"), "--smoke-test", str(report), env=env)
    result = json.loads(report.read_text(encoding="utf-8"))
    if result["samples"] != 1600 or result["backend"] != "whisper.cpp":
        raise RuntimeError(f"Frozen application smoke test failed: {result}")
    if arch == "arm64" and not result["gpu_supported"]:
        raise RuntimeError(
            "The Apple Silicon app must bundle a Metal-enabled whisper.cpp runtime"
        )

    if os.environ.get("PARROTIA_SMOKE_MODEL_NAME"):
        for scenario in ("complete", "active"):
            run(
                str(app / "Contents/MacOS/parrotia-gui"),
                "--lifecycle-smoke-test",
                str(generated / f"lifecycle-{scenario}.json"),
                scenario,
                env=env,
                timeout=60,
            )

    output = ROOT / "dist/installer"
    output.mkdir(parents=True, exist_ok=True)
    dmg = output / f"ParrotIA-{__version__}-macos-{arch}.dmg"
    with tempfile.TemporaryDirectory(prefix="parrotia-dmg-") as tmp:
        staging = Path(tmp)
        shutil.copytree(app, staging / app.name, symlinks=True)
        (staging / "Applications").symlink_to("/Applications")
        run(
            "hdiutil",
            "create",
            "-volname",
            "ParrotIA",
            "-srcfolder",
            str(staging),
            "-ov",
            "-format",
            "UDZO",
            str(dmg),
        )
    if args.sign_identity:
        run(
            "codesign", "--force", "--sign", args.sign_identity, "--timestamp", str(dmg)
        )
    if args.notary_profile:
        run(
            "xcrun",
            "notarytool",
            "submit",
            str(dmg),
            "--keychain-profile",
            args.notary_profile,
            *(["--keychain", args.notary_keychain] if args.notary_keychain else []),
            "--wait",
        )
        run("xcrun", "stapler", "staple", str(dmg))
        run(
            "spctl",
            "--assess",
            "--type",
            "open",
            "--context",
            "context:primary-signature",
            str(dmg),
        )
    run("hdiutil", "verify", str(dmg))
    print(f"Built {dmg}")


if __name__ == "__main__":
    main()
