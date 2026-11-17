cask "parrotia" do
  arch arm: "arm64", intel: "x86_64"

  version "1.5.3"
  sha256 arm:   "c8ce2588c471e901d4bb6b5585b55b14a6a1b12e6be6e4cd0eaf010394223a45",
         intel: "de7f8b048c56276b7ead5736d2db57b047d17d1276ebd5954f66029c6c40d7c4"

  url "https://github.com/igorbispo99/ParrotIA/releases/download/v#{version}/ParrotIA-#{version}-macos-#{arch}.dmg"
  name "ParrotIA"
  desc "Local audio and video transcription with Whisper"
  homepage "https://github.com/igorbispo99/ParrotIA"

  depends_on macos: :sonoma

  app "ParrotIA.app"
end
