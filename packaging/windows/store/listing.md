# Microsoft Store listing: ParrotIA (en-us)

Text for the Partner Center *Store listing* and *Submission options* pages. Image
files are in `assets/` (regenerate with `python packaging/windows/store/make_assets.py`).
Everything here must stay true to the shipped app; update it with each release.

## Description

The dependency note comes first because Store policy 10.2.4 requires it.

```text
Needs a one-time download of a speech-recognition model from Hugging Face the first time you use it (about 75 MB for the smallest model, about 1.6 GB for the default). After that, transcription works offline.

ParrotIA turns spoken audio and video into text on your own PC. Choose a recording, or a whole folder, pick a model, and get a transcript next to the original file. Your files are never uploaded.

- Transcribe one file or a whole folder in one go
- Automatic language detection, or choose the language yourself
- Save as plain text (TXT), Markdown (MD), subtitles (SRT, VTT) or JSON
- Whisper models from tiny (fastest) to large-v3 (most accurate), with the fast and accurate large-v3-turbo as the default
- No account, no subscription, no ads and no tracking
- Free and open source under the AGPL-3.0 license

ParrotIA runs OpenAI's open-source Whisper speech-recognition models on your computer through faster-whisper. It is an independent project and is not affiliated with OpenAI or Hugging Face.
```

## Short description (up to 1000 characters)

```text
Free, private audio and video transcription that runs on your PC. Pick a file or a folder and get TXT, Markdown, SRT, VTT or JSON.
```

## What's new in this version

```text
First release on the Microsoft Store.
```

## Search terms (up to 7)

`transcription`, `whisper`, `speech to text`, `subtitles`, `srt`, `audio to text`, `offline transcriber`

## Copyright and trademark info

```text
Copyright (C) 2026 Igor Bispo. Licensed under the GNU AGPL v3 or later.
```

## Additional license terms

Store agreement section 4.i: the developer licenses the app to customers, and without
supplied terms the Standard Application License Terms apply, which forbid copying
and redistribution that the AGPL grants. Supply these terms.

```text
ParrotIA is free software licensed under the GNU Affero General Public License, version 3 or later. You may use, study, share and modify it under those terms.

License text: https://github.com/igorbispo99/ParrotIA/blob/main/LICENSE
Source code: https://github.com/igorbispo99/ParrotIA

Third-party components are used under their own licenses, listed in THIRD_PARTY_NOTICES.txt in the app's install folder and in the app under "Third-party notices". On request, the maintainer provides the corresponding source of the LGPL and GPL libraries it bundles; see that file for how to ask.
```

## Images

| Slot in Partner Center | File | Notes |
| --- | --- | --- |
| Screenshots (desktop, at least 1366x768) | `assets/screenshot-1920x1080.png` | The window on a plain background. It predates the privacy/license links added at the bottom of the window; replace it with a capture from the Windows build when convenient. |
| Store logo, 1:1 | `assets/logo-300x300.png` and `assets/logo-1080x1080.png` | Scaled up from a 256x256 source, so soft. Replace with art made from a vector original if one exists. |

The README banner (`docs/banner.png`) contains placeholder "lorem ipsum" text in its artwork, so it is not used for the Store.

## Properties and declarations chosen in Partner Center

- Category: Productivity; secondary: Utilities and tools.
- Free, all markets, public audience.
- Privacy: *Yes, the product uses personal information*. The only personal data
  involved is the IP address revealed to Hugging Face when a model is downloaded.
  Privacy policy URL: `https://github.com/igorbispo99/ParrotIA/blob/main/docs/privacy.md`.
- Support: website and support URL are the project and its issue tracker; no
  email address, phone or street address is published.
- Generative AI declaration: checked. The app creates text transcripts from audio
  with an AI model (Whisper). It runs locally and produces no online content.
- OneDrive backup of app data: off (model files are very large).
- Not marked as tested for accessibility guidelines.
- Minimum memory 4 GB, recommended 8 GB (an estimate; revise after testing).
- Age rating (IARC questionnaire, all-other-apps type): all answers "No".
  Result: IARC 3+, ESRB Everyone, PEGI 3, USK all ages, ClassInd all ages.

## Notes for certification

```text
No sign-in or account is needed.

To test: start ParrotIA, choose the model "tiny" (about 75 MB, to avoid the 1.6 GB default), click "File...", pick any short audio or video file, and click "Transcribe". On first use the app downloads the chosen model from Hugging Face, so the test machine needs internet access once. The transcript appears in the window and is saved next to the source file. A Windows Sound Recorder clip works as test input.

The package declares the runFullTrust capability because ParrotIA is a classic desktop application packaged as MSIX. It reads and writes the audio, video and transcript files the user selects and runs native inference libraries. It requests no other capability.

Generative AI disclosure: ParrotIA runs the open-source Whisper speech-recognition model locally to create text transcripts from the user's own audio. It generates no content online. Problems can be reported at https://github.com/igorbispo99/ParrotIA/issues.

The model download and the data it reveals are described in the privacy policy. The app has no accounts, advertising, analytics or update checks.
```
