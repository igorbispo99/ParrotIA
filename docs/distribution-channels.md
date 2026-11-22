# Distribution channels and launch kit

[Documentation](README.md) · [Store submission plan](store-submission-plan.md) · [Installation](installation.md)

Status as of **21 November 2026**, for ParrotIA **1.5.3**. The first section
records what has been submitted and what each channel is waiting for. The
second holds ready-to-edit copy for announcing ParrotIA; nothing in it has
been posted.

## Channel status

| Channel | State | Waiting for | Next action |
| --- | --- | --- | --- |
| Snap Store | Live (AMD64, ARM64) | — | Keep releases in step with GitHub |
| Homebrew tap | Live | — | Official cask needs a signed, notarized app ([macOS roadmap](mac-app-store-roadmap.md)) |
| PyPI | Live | — | — |
| Fedora COPR | Live | — | — |
| Official Fedora | In review, needs a sponsor | Reviewer/sponsor | See [store submission plan](store-submission-plan.md) |
| WinGet | [PR #486056](https://github.com/microsoft/winget-pkgs/pull/486056) open, `IgorBispo.ParrotIA` 1.5.3 | Microsoft's last pipeline step and moderator merge | Reply to moderator comments if any; then submit 1.5.4+ by PR |
| AlternativeTo | Submitted to the free review queue, listed as an alternative to Vibe Transcribe | Editorial review | Check the submissions page; add screenshots if editors ask |
| AUR (`parrotia-bin`) | Recipe tested; **not published** | An AUR account (registration was reported closed on 21 November) | Re-check registration, add the SSH key, push `packaging/aur/parrotia-bin` |
| Arch package on GitHub | `parrotia-bin-1.5.3-1-x86_64.pkg.tar.zst` is attached to the 1.5.3 release | — | Documented in [installation](installation.md#arch-linux) |
| Flathub | Not started | A human maintainer | See below |
| Code signing | Workflows and policy prepared, **not enabled**; SignPath application submitted 21 November 2026 | SignPath Foundation decision (Windows) and an Apple Developer ID (macOS) | Follow [code signing setup](code-signing.md) |
| Microsoft Store | Deferred | Trusted code signing of the installer and every bundled executable | Revisit with a signing certificate |
| Mac App Store | Planning only | Developer account, rights review, sandbox prototype | [Roadmap](mac-app-store-roadmap.md) |

### WinGet evidence

PR 486056 passed Microsoft's pipeline stages 01–09: pull-request, manifest,
URL, domain, policy, catalog content, installer scan, **installation**, and
installer metadata. The manifest is in `packaging/winget/IgorBispo.ParrotIA/1.5.3`
and uses the existing per-user Inno Setup installer.

A separate run on a GitHub-hosted Windows runner hung during silent
installation because Windows SmartScreen (`CHXSmartScreen.exe`) was waiting
on the unsigned installer; the same manifest installed cleanly in Microsoft's
pipeline. Treat that as a limit of that runner, not a manifest defect.
Signing the installer would remove the SmartScreen prompt for real users too.

For each later release, copy the manifest folder to the new version, update
`PackageVersion`, `InstallerUrl` and `InstallerSha256`, and open a PR.
`wingetcreate update IgorBispo.ParrotIA --version <v> --urls <url> --submit`
automates this.

### AUR

`packaging/aur/parrotia-bin` builds from the released `.deb` files and checks
their SHA-256 sums. It installed on Arch, and transcribed a speech sample to
TXT, Markdown and SRT, after bundled `libfontconfig` was removed in favour of
Arch's own. Publishing requires an AUR account, which this project does not
have yet. Once it does:

```bash
git clone ssh://aur@aur.archlinux.org/parrotia-bin.git
cp packaging/aur/parrotia-bin/{PKGBUILD,.SRCINFO} parrotia-bin/
cd parrotia-bin && git add PKGBUILD .SRCINFO && git commit -m "Add parrotia-bin 1.5.3" && git push
```

Regenerate `.SRCINFO` with `makepkg --printsrcinfo > .SRCINFO` after any edit.

### Flathub

Flathub's policy prohibits AI assistance on the manifest and submission text,
and asks authors to disclose known AI-generated material in the app. The
Flatpak manifest and submission PR therefore have to be written by the
maintainer personally. The groundwork already exists: desktop ID
`io.github.igorbispo99.ParrotIA`, icon, AppStream metadata and a screenshot.
Points to test in the sandbox: model downloads, batch folder access, and saving
transcripts beside the source file. Read the current
[requirements](https://docs.flathub.org/docs/for-app-authors/requirements)
and [submission process](https://docs.flathub.org/docs/for-app-authors/submission)
before starting.

### Not yet pursued

- **Scoop / Chocolatey:** both would reach more Windows users. Neither has been
  tested against the unsigned Inno installer; Scoop's official Extras bucket has
  its own acceptance rules, so a project-owned bucket is the safer first step.
- **nixpkgs:** possible for the Linux build, but bundled-binary packages are
  disfavoured; a source build would need the whisper.cpp or CTranslate2 stack.
- **GitHub repository metadata:** at the time of writing the repository has no
  topics and no homepage. Suggested topics: `whisper`, `transcription`,
  `speech-to-text`, `subtitles`, `srt`, `offline`, `privacy`, `desktop-app`,
  `whisper-cpp`, `faster-whisper`, `customtkinter`.

## Where to announce

| Place | Why | Notes |
| --- | --- | --- |
| [awesome-voice-typing](https://github.com/primaprashant/awesome-voice-typing) | Lists local Whisper desktop apps such as Buzz and Vibe | Read its contribution rules; fits as an offline desktop transcriber |
| [Awesome Whisper Apps](https://github.com/danielrosehill/Awesome-Whisper-Apps) | Directory of Whisper GUIs | Open an issue or PR as its README directs |
| [sindresorhus/awesome-whisper](https://github.com/sindresorhus/awesome-whisper) | Large, mostly Apple-focused list | Only if it accepts cross-platform FOSS apps; check its guidelines |
| Show HN, r/opensource, r/selfhosted, r/DataHoarder | People who care about offline tools | Follow each community's self-promotion rules; disclose that you are the author |

Post only when a clean install works on the platform the audience uses, and be
present to answer questions for the first day.

## Launch copy (drafts)

### Show HN

> **Show HN: ParrotIA – local audio/video transcription with Whisper, no accounts**
>
> I built ParrotIA because I wanted to transcribe recordings without uploading
> them anywhere. It's a desktop app (Windows, macOS, Linux) and a CLI. You pick
> a file or a whole folder, choose a Whisper model, and get TXT, Markdown, SRT,
> VTT or JSON next to the source. After the one-time model download it works
> offline. It uses Metal on Apple Silicon, CUDA on NVIDIA, or the CPU.
>
> Installers bundle Python and the media codecs: Windows setup, macOS DMGs, `.deb`/
> `.rpm`, Snap, a Homebrew tap, and `pip install parrotia`. AGPL-3.0.
>
> Repo: https://github.com/igorbispo99/ParrotIA — feedback on model defaults and
> the installers is very welcome.

### Short description (directories, 160 characters)

Free desktop app that transcribes audio and video locally with Whisper. Batch folders, SRT/VTT export, no accounts or API keys, works offline after setup.

### Release-announcement paragraph

ParrotIA is a free, open-source desktop transcriber. Drop in a recording or a
folder, pick a Whisper model, and export text, Markdown, subtitles or JSON.
Your audio stays on your computer. Install it from GitHub Releases, `winget`
(once approved), Snap, Homebrew, Fedora COPR or PyPI.

### Claims to keep accurate

- The default `large-v3-turbo` model download is about 1.6 GB; smaller models
  exist. Do not describe the first run as instant.
- "Offline" applies after the model is downloaded.
- Do not publish speed comparisons without a recorded benchmark
  (`parrotia` CLI benchmark mode) and the hardware it ran on.
- The macOS build is ad-hoc signed and triggers Gatekeeper until it is signed and
  notarized; say so rather than letting users discover it.
