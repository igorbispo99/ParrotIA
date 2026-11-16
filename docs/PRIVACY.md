# ParrotIA privacy policy

Effective date: 16 November 2026. This policy covers every ParrotIA build: the Microsoft Store app, the Windows and Linux installers, the Snap, the Fedora package and the Python package on PyPI.

ParrotIA is a free, open-source application maintained by Igor Bispo. It transcribes audio and video files on your own computer.

## What ParrotIA does not do

- It has no user accounts, sign-in or API keys.
- It sends no analytics, telemetry, crash reports or advertising identifiers.
- It never uploads your audio, video or transcripts. Speech recognition runs entirely on your device.
- The developer receives no data about you or your use of the app.

## The one network connection: model downloads

The first time you use a speech model, ParrotIA downloads it from [Hugging Face](https://huggingface.co/) and stores it on your computer. Model sizes range from about 75 MB (`tiny`) to about 3 GB (`large-v3`); the default `large-v3-turbo` is about 1.6 GB. Later transcriptions with that model work offline.

The download is an ordinary HTTPS request to Hugging Face. Like any web request, it reveals your IP address, plus a user-agent header naming the download library and its version. No audio, file names or transcripts are sent. Hugging Face handles that request under its own [privacy policy](https://huggingface.co/privacy).

## Data stored on your computer

- **Speech models:**
  - Microsoft Store app: in its private app storage. Windows deletes it when you uninstall the app.
  - Other Windows builds: `%USERPROFILE%\.cache\huggingface`, unless you set `HF_HOME`.
  - Linux builds: `~/.cache/huggingface`, or ParrotIA's whisper.cpp model folder.
- **Transcripts:** saved where you choose. By default that is beside the original file, in the formats you select (txt, md, srt, vtt, json).
- **Right-click queue:** the Windows "Transcribe on Parrot" command keeps a short list of the files you selected in local app data, only while they are being transcribed.

You can delete any of these files at any time. ParrotIA keeps no other records.

## Children

ParrotIA collects no personal information from anyone, including children.

## Changes

Changes to this policy are published in this file, with a new effective date. Its history is public in the [ParrotIA repository](https://github.com/igorbispo99/ParrotIA/commits/main/docs/PRIVACY.md).

## Contact

Open an issue at <https://github.com/igorbispo99/ParrotIA/issues>.
