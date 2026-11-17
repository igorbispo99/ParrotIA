cask "parrotia" do
  arch arm: "arm64", intel: "x86_64"

  version "1.5.2"
  sha256 arm:   "ac73f89f62cb0f8547c4091cbdeeeee6958dc8c8dcc4d8d464b16ac757914663",
         intel: "58465f4b8218784da8851e3603541352b12e85c123161a2c3d3c983ed53536a9"

  url "https://github.com/igorbispo99/ParrotIA/releases/download/v#{version}/ParrotIA-#{version}-macos-#{arch}.dmg"
  name "ParrotIA"
  desc "Local audio and video transcription with Whisper"
  homepage "https://github.com/igorbispo99/ParrotIA"

  depends_on macos: :sonoma

  app "ParrotIA.app"
end
