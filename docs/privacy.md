# Privacy policy

[Documentation](README.md) · [Code signing policy](code-signing-policy.md)

Effective **22 November 2026**, for ParrotIA 1.5.3 and later.

ParrotIA is a desktop application and command-line tool that transcribes audio
and video files on your own computer. This page says what it does with your
data. The short version: your recordings and transcripts never leave your
computer, and ParrotIA has no accounts, advertising or analytics.

## What stays on your computer

- **Your audio and video files** are read from the place you choose and are never
  uploaded.
- **Transcripts** are written next to the source file or in the folder you pick.
  Nothing sends them anywhere.
- **Downloaded models** are kept on your device and stay when you uninstall the
  app. On Windows they are in the Hugging Face cache in your user folder
  (normally `%USERPROFILE%\.cache\huggingface\hub`), which other tools that use
  that cache share. On macOS they are in
  `~/Library/Application Support/parrotia/models` and on Linux in
  `~/.local/share/parrotia/models`. Delete these folders to remove the models.
- **A short-lived list of file paths** may be written to your user data folder
  when you use the Windows Explorer action, so the app can open the files you
  selected.

## The only network connection

The first time you use a Whisper model, ParrotIA downloads it from
[Hugging Face](https://huggingface.co). That request necessarily reveals your IP
address and which model file you asked for to Hugging Face and to the networks
the request passes through. ParrotIA turns off the optional usage information
that the Hugging Face client library would otherwise add to those requests.
Hugging Face handles the request under its own
[privacy policy](https://huggingface.co/privacy). After a model is downloaded,
transcription with it works offline.

ParrotIA makes no other network connections: it does not check for updates, send
crash reports, or contact any server of the developer.

## Microsoft Store

If you install ParrotIA from the Microsoft Store, Microsoft handles the purchase
and installation under its own terms and privacy statement, and may collect data
such as acquisition, usage and crash information. The developer can receive
aggregate analytics and error reports from Microsoft through Partner Center. The
developer uses them only to fix problems and does not combine them with other
data.

## Personal information

ParrotIA does not ask for, collect or store personal information, and the
developer receives none of your files, transcripts or account details. Because
recordings can contain personal information, remember that transcripts you create
are ordinary files that you control.

## Children

ParrotIA is a general-purpose tool and is not directed to children.

## Changes and contact

If this policy changes, the new version is published at this address with a new
effective date. Questions or requests: open an issue at
[github.com/igorbispo99/ParrotIA/issues](https://github.com/igorbispo99/ParrotIA/issues).
