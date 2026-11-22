# Code signing policy

[Documentation](README.md) · [Installation](installation.md) · [Signing setup for maintainers](code-signing.md)

**Status (21 November 2026): Windows installers are not code-signed yet, and
macOS builds are not notarized yet.** An application to the SignPath Foundation
for free Windows signing was submitted on 21 November 2026 and is pending.
Windows may show a SmartScreen warning and macOS Gatekeeper may ask for
confirmation. This policy describes how releases will be signed once the
signing services below are enabled.

The Homebrew cask and the WinGet manifest pin the SHA-256 checksums of the
files attached to each [GitHub release](https://github.com/igorbispo99/ParrotIA/releases),
and the package managers verify them before installing.

## What is signed

- **Windows:** `parrotia-gui.exe` and the `ParrotIA-<version>-windows-x64-setup.exe`
  installer, both built from this repository. Third-party libraries bundled in
  the installer (Python, FFmpeg/PyAV, ONNX Runtime, CTranslate2 and others) are
  upstream binaries and are not re-signed.
- **macOS:** `ParrotIA.app` and the DMG, signed with an Apple Developer ID
  certificate and notarized by Apple.
- Release binaries are built by GitHub Actions from the tagged commit. A signing
  request is created only by the release workflow, never from a pull request.

## Signing provider

Windows signing is planned through the SignPath Foundation's free program for
open source projects. When it is enabled, this section applies:

> Free code signing provided by [SignPath.io](https://signpath.io), certificate
> by [SignPath Foundation](https://signpath.org).

The certificate is issued to SignPath Foundation, which is therefore the
publisher shown by Windows. macOS builds use the project owner's own Apple
Developer ID.

## Team roles

ParrotIA currently has a single maintainer, who holds every role. Multi-factor
authentication is required on GitHub and on the signing service.

| Role | Responsibility | Member |
| --- | --- | --- |
| Author | Writes and commits code | [igorbispo99](https://github.com/igorbispo99) |
| Reviewer | Reviews contributions from other people before they are merged | [igorbispo99](https://github.com/igorbispo99) |
| Approver | Manually approves each signing request for a release | [igorbispo99](https://github.com/igorbispo99) |

If more maintainers join, the Reviewer and Approver roles will move to people
other than the author of a change where possible.

## Privacy policy

ParrotIA transcribes audio and video on your computer. It does not collect
telemetry, create accounts, or send your files or transcripts anywhere. The only
network request the application makes is downloading a Whisper model from
[Hugging Face](https://huggingface.co) the first time you use that model;
later transcription runs offline.

## Installing and removing

The Windows installer is a per-user Inno Setup installer that adds Start menu
and optional desktop and Explorer shortcuts, and lists ParrotIA in **Apps →
Installed apps** for removal. It needs no administrator rights and does not
change system or security settings; the optional Explorer right-click entries
are written under the current user's registry only. Transcripts and the model
cache are kept on removal.

## Reporting problems

Report a suspected problem with a signed release through the
[issue tracker](https://github.com/igorbispo99/ParrotIA/issues). The maintainer
will cooperate with the signing provider in any investigation.
