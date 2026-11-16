# Microsoft Store listing (Partner Center text)

This file holds ready-to-paste values for each Partner Center field, written against Store Policies 7.20. The plan and status are in [microsoft-store-plan.md](microsoft-store-plan.md). Keep the description free of URLs; links go in their own fields.

## Properties

| Field | Value |
| --- | --- |
| Category | Productivity (subcategory: none). Utilities & tools is the alternative. |
| Privacy policy URL | `https://github.com/igorbispo99/ParrotIA/blob/main/docs/PRIVACY.md` |
| Website | `https://github.com/igorbispo99/ParrotIA` |
| Support contact | `https://github.com/igorbispo99/ParrotIA/issues` |
| Accesses, collects or transmits personal information? | No. A policy is still required for Win32 apps (10.5.1), so supply the URL above. |
| Product declarations | Leave all unchecked unless Partner Center adds a generative-AI declaration; see the AI note below. |
| System requirements | x64 processor. Not yet measured: record memory use for `tiny` and `large-v3-turbo` on a clean PC before filling the memory fields. |

## Store listing (English)

**Product name:** ParrotIA

**Short description** (under 270 characters):

> Transcribe audio and video privately on your PC. Whisper speech recognition runs locally: no account, no upload, no subscription. Export text, subtitles or JSON.

**Description:**

```text
Speech models are downloaded once from Hugging Face the first time you use them (about 75 MB to 3 GB, depending on the model; the default model is about 1.6 GB). After that, ParrotIA transcribes offline.

ParrotIA turns recordings into text on your own computer. It uses OpenAI's Whisper speech recognition models through faster-whisper, so your audio never leaves your PC. There is no account, no cloud service and no usage limit.

Choose one file or a whole folder, pick a model and language, and ParrotIA writes the transcript beside each file or to a folder you choose. Save plain text, Markdown, SRT or WebVTT subtitles, or JSON with timestamps, in any combination.

In File Explorer, select one or more audio or video files, right-click and choose "Transcribe on Parrot" to transcribe them without opening the main window. On Windows 11 the command is right in the main context menu.

Models range from tiny (fastest) to large-v3 (most accurate), plus the fast large-v3-turbo and distil-large-v3. Whisper understands about 100 languages and can detect the language automatically. Transcription runs on the processor; larger models are slower on modest hardware.

ParrotIA is free and open-source software under the GNU Affero General Public License v3.0 or later.
```

**Features** (one per line, 200 characters each at most, no bullets):

```text
Fully local speech recognition: audio and transcripts never leave your PC
No account, subscription or API key
Works offline after a one-time model download
Transcribe a single file or every audio and video file in a folder
Right-click "Transcribe on Parrot" in File Explorer, for one or many files
Export txt, Markdown, SRT, WebVTT and JSON with timestamps
Automatic language detection for about 100 languages
Choose speed or accuracy: tiny to large-v3, large-v3-turbo and distil-large-v3
Live progress with cancel; the window stays responsive
Free and open source (AGPL-3.0-or-later)
```

**Keywords** (up to 7): `transcription`, `speech to text`, `whisper`, `subtitles`, `srt`, `offline`, `audio to text`

**Screenshots:** 4–6 PNG at 1920×1080 or larger (minimum 1366×768), captured on Windows from the installed MSIX build. Show:

1. The main window with a file selected.
2. A finished transcript preview.
3. The output format and model options.
4. The Explorer right-click command.

Don't overlay text or logos. For the 300×300 Store tile icon, upload `dist/msix/ParrotIA-store-icon-300.png`, which the MSIX build writes.

**Additional license terms:**

```text
ParrotIA is licensed under the GNU Affero General Public License, version 3 or (at your option) any later version: https://github.com/igorbispo99/ParrotIA/blob/main/LICENSE

The complete corresponding source code for each release is available at https://github.com/igorbispo99/ParrotIA/releases. Third-party components are distributed under their own licenses, listed in the source repository.
```

## Age rating (IARC questionnaire)

Category: **Utility / productivity app** (not a game). Expected answers:

| Question | Answer |
| --- | --- |
| Violence, sexual content, profanity, drugs, gambling | No |
| User-to-user interaction or communication | No |
| Shares user location or personal information | No |
| Digital purchases | No |
| Unrestricted internet access (e.g. a browser) | No. It downloads only speech models. |

These answers should produce the lowest rating band in every region.

## Submission options

**Restricted capability justification (`runFullTrust`):**

```text
ParrotIA is a Win32 desktop application (Python with Tk, frozen by PyInstaller) packaged as MSIX. runFullTrust is required to launch its desktop executable and native speech-recognition libraries (CTranslate2, ONNX Runtime, FFmpeg via PyAV). It declares no other restricted capability.
```

**Notes for certification:**

```text
No account or sign-in is needed.

1. Launch ParrotIA, click "File…" and choose any short audio or video file (for example a 30-second MP3).
2. For a quick test, set Model to "tiny" (about 75 MB) or "base" (about 145 MB). The first use of a model downloads it once from huggingface.co; the default large-v3-turbo is about 1.6 GB.
3. Click Transcribe. The transcript appears in the preview, and the files are saved next to the input.

File Explorer integration: right-click one or more audio/video files and choose "Transcribe on Parrot" (in the main context menu on Windows 11). A small progress window transcribes them with the default settings.

Models are stored in the app's private storage and removed on uninstall.
```

## AI disclosure (policy 11.16)

ParrotIA produces a transcript of the user's own recording. It does not generate open-ended content from prompts. Whisper is still a generative sequence-to-sequence model, so declare it if Partner Center asks about generative AI. The listing already describes the technology, and user reports go to the GitHub issues URL above.
