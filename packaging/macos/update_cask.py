"""Generate a Homebrew cask from the exact DMGs prepared for a release."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from parrotia import __version__  # noqa: E402


def render_cask(version: str, artifacts: Path) -> str:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Expected a stable version such as 1.5.1")
    checksums = {}
    for arch in ("arm64", "x86_64"):
        path = artifacts / f"ParrotIA-{version}-macos-{arch}.dmg"
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        checksums[arch] = digest.hexdigest()
    return f'''cask "parrotia" do
  arch arm: "arm64", intel: "x86_64"

  version "{version}"
  sha256 arm:   "{checksums["arm64"]}",
         intel: "{checksums["x86_64"]}"

  url "https://github.com/igorbispo99/ParrotIA/releases/download/v#{{version}}/ParrotIA-#{{version}}-macos-#{{arch}}.dmg"
  name "ParrotIA"
  desc "Local audio and video transcription with Whisper"
  homepage "https://github.com/igorbispo99/ParrotIA"

  depends_on macos: :sonoma

  app "ParrotIA.app"
end
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=__version__)
    parser.add_argument("--artifacts", type=Path, default=ROOT / "dist/installer")
    parser.add_argument("--output", type=Path, default=ROOT / "Casks/parrotia.rb")
    args = parser.parse_args()
    cask = render_cask(args.version, args.artifacts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(cask, encoding="utf-8")
    print(f"Generated {args.output}")


if __name__ == "__main__":
    main()
