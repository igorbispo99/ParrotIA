# Microsoft Store roadmap

[Documentation](README.md) · [Distribution channels](distribution-channels.md) · [Code signing setup](code-signing.md)

ParrotIA **1.5.3** is **published on the Microsoft Store** (certified and published
on 23 November 2026): [https://apps.microsoft.com/detail/9NXSSCQKW2XR](https://apps.microsoft.com/detail/9NXSSCQKW2XR).
The product name is reserved and the package is signed by Microsoft after
certification. Submitted on 22 November 2026 with manual publication, so the app
went live only when the maintainer clicked *Publish now*.

Publishing as MSIX removes the need for a code signing certificate: after
certification the Store re-signs the package with a Microsoft certificate.
Submitting the existing Inno Setup `.exe` instead would require the project's
own trusted signature, so it is not the plan. The Store would add a search
listing and automatic updates, and a Microsoft-signed package avoids the
unsigned-installer warning. It does not replace the direct download.

## Reserved product

| Field | Value |
| --- | --- |
| Product | ParrotIA (MSIX app), published |
| Store ID | `9NXSSCQKW2XR` |
| Identity name | `IgorBispo.ParrotIA` |
| Publisher | `CN=8D013184-D3B0-4A06-98A9-CD149E2D2315` |
| Publisher display name | Igor Bispo |
| Package family name | `IgorBispo.ParrotIA_rnmjmj8qbbenr` |

These values appear in every published package, so they are not secrets. The
reservation lapses on **22 February 2027** if no submission has been made.

## Prototype status

`packaging/windows/msix.py` wraps the frozen bundle in an MSIX with a
full-trust manifest and logos generated from the application icon.
`packaging/windows/test-msix.ps1` signs a test package with a throwaway
certificate, installs it, and runs the app's smoke test inside the package. The
**Microsoft Store package** workflow runs both on a Windows runner and keeps the
test package as an artifact. The test package uses a placeholder identity and
**cannot be submitted**.

First result (GitHub-hosted `windows-latest`, 22 November 2026): `makeappx`
packed the bundle, the test-signed package installed under
`C:\Program Files\WindowsApps`, and the frozen app decoded 1,600 audio samples
when launched inside the package. The CI artifact is about 109 MB. This shows
the manifest and packaging are valid for a sideloaded test package; it does not
cover Store certification, the Explorer action, or a real transcription with a
downloaded model.

## Steps

| # | Step | Owner | Notes |
| --- | --- | --- | --- |
| 1 | Register and verify the Partner Center account (**done**) | Project owner | Microsoft verified the profile and granted full Partner Center access. |
| 2 | Reserve the product name (**done**: ParrotIA) | Project owner | Partner Center → New product → MSIX → check availability. A reservation lasts three months. Copy the *Product identity* values (Name, Publisher, Publisher display name). |
| 3 | Build the submission package | Developer | `python packaging/windows/msix.py --identity-name … --publisher … --publisher-display-name …` with the Partner Center values. The version is `major.minor.patch.0`; the Store reserves the last part. |
| 4 | Test the package | Developer | Run the workflow, then install on a real Windows 10/11 machine and exercise a full transcription (model download, folder input, export beside the source). |
| 5 | Complete the listing | Project owner | Pricing (free), properties, age rating (IARC questionnaire), packages, description, screenshots and logos, and notes for certification. |
| 6 | Submit and respond | Project owner | Certification is documented as taking up to three business days, with the listing visible about 15 minutes after approval. |

## Behaviour that changes in a packaged app

- **Where models are stored.** On Windows the models come from faster-whisper and
  live in the Hugging Face cache in the user's profile folder
  (`%USERPROFILE%\.cache\huggingface\hub`), not under `LocalAppData`. Packaged
  apps redirect only new files under the AppData folders, so the cache is expected
  to be shared and to survive uninstalling; the CI test checks that a packaged
  process can write to the profile folder and that the file is visible outside the
  package. Only the Windows Explorer queue file lives under `LocalAppData`, and the
  Store edition has no Explorer action.
- **No Explorer right-click action in the first Store edition.** The action is a
  per-user registry entry created by the Inno installer. A packaged app would
  need a different mechanism (a registered Explorer command component).
- **The install folder is read-only.** The app must not write next to its own
  executable. Outputs beside a user's input file are documented as allowed when
  the user has permission; confirm on the packaged build.
- **`runFullTrust` is a restricted capability.** The package requests only this
  one. Prepare a short justification: a desktop application that reads and writes
  user-selected audio, video and transcript files.

## Store Policies read on 22 November 2026

From [Microsoft Store Policies](https://learn.microsoft.com/en-us/windows/apps/publish/store-policies)
version 7.20 (published 15 September 2026, effective 22 October 2026). Sections
10.1 to 10.13 were read in full; later sections, including section 11, were only
read in summary, so treat those points as secondhand.

| Policy | What it means for ParrotIA |
| --- | --- |
| 10.5.1 Privacy | A privacy policy URL is required when a product accesses or transmits personal information, and the text names Desktop Bridge and Win32 products as types that must have one. Plan to provide one at submission. Whether recorded speech counts as personal information is an inference, not stated. |
| 10.2.4 Dependencies | Dependencies on software the app does not integrate must be disclosed at the start of the description. State the first-use model download from Hugging Face there. |
| 10.2.2 Dynamic code | Downloading a model is data, not code, but the description should say what is downloaded and why. |
| 10.2.7 Uninstall | A clean uninstall must be possible. A packaged app removes its files and redirected AppData. |
| 10.6 Capabilities | Declared capabilities must relate to the product's function. `runFullTrust` is not mentioned by name; the package requests only that one. |
| 10.1.1 Title | The title must be unique and not contain marketing or descriptive text. "ParrotIA" is a bare name. Trademark clearance was not checked. |
| 11.1 and 11.11 Rating | The IARC questionnaire is completed at submission. Content must not exceed PEGI 12 or ESRB Everyone 10+. |
| 11.16 Generative AI | Products that generate output dynamically in response to input must disclose live generative AI use. It is unclear whether Whisper speech-to-text counts; read the section and answer the Partner Center disclosure question carefully. |

No policy text mentions GPL, AGPL or copyleft, but the policies are not the only
terms; see the agreement review below.

## App Developer Agreement review (22 November 2026)

Read from the PDF of [App Developer Agreement v8.11](https://go.microsoft.com/fwlink/?linkid=528905)
(published 17 March 2026, effective 17 April 2026): the 52-page text was
extracted and the main body (clauses 1 to 12, pages 1 to 25) and the US/Canada
Standard Application License Terms (Exhibit G) were read. The tax exhibits, the
Edge add-on and preload exhibits, and the other regional license variants were
not read. This is a reading of the text, not legal advice.

**What favours the AGPL.** The agreement defines FOSS as software under an
OSI-approved license, which includes AGPL-3.0. The grant of rights to Microsoft
excludes "any material subject to any FOSS licenses" (4.b). Microsoft acts as the
developer's agent and the developer, not Microsoft, is the distributor of the app
(4.a.i), so source-offer and notice duties under the AGPL stay with the project.
Nothing found requires ParrotIA to be proprietary.

**What has to be done or watched.**

| Clause | Requirement | Action |
| --- | --- | --- |
| 4.i License to Customer | The developer licenses the app to customers. If no license is supplied, the Standard Application License Terms apply. Those forbid reverse engineering, copying beyond the terms, making the app available to others to copy, and transferring it, which contradict AGPL rights. A supplied license must give download and usage rights no more restrictive than the Microsoft Usage Rules. | Supply the AGPL-3.0 text, or a link to it, as the license terms in the Store listing. Do not leave the default. |
| 4.c and 5.c FOSS and third-party rights | The developer is solely responsible for compliance with every FOSS license in the app, including source availability, and for ensuring Microsoft has the rights it needs. | Ship third-party notices and source offers for the bundled native libraries (next section). |
| 10.c Duty to defend | The developer defends and indemnifies Microsoft and affiliates against third-party claims about infringement, the app's functionality or inability to use it, product liability and misleading advertising. The clause states no cap, and the obligation is the developer's, which on an Individual account is the person. | Read it yourself before accepting and decide whether you are comfortable as an individual; consider advice. |
| 7.d Warranties | The developer warrants that all required third-party consents and licenses for distributing the app in the Store have been obtained. | Confirm every bundled component allows redistribution in this form. |
| 2 Store Account | If distribution relates to the developer's business, trade or profession, the account must be a Company account. Choosing Individual is a declaration of status. | Confirm that an individual account fits how ParrotIA is run and promoted. |
| 4.h Privacy Policy | A policy is required if the app collects or transmits personal information, and the developer must keep a prominent link to it in a reasonable place such as inside the app, plus the Store page. | Publish a privacy page and add a link in the app (code change). |
| 3.k and 12.n Removal and changes | Microsoft may remove or suspend an app for any reason, and may update the agreement at any time. Termination is possible on 60 days' notice. | Keep the other distribution channels; do not depend on the Store. |
| 12.f Law and venue | Washington State law; exclusive venue in King County, Washington. Claims must be filed within one year. | Note, for an individual outside the United States. |
| 5.b Export | Controlled technology used by the app must be disclosed to Microsoft. | The app's network use is the model download; confirm with the export classification of the bundled libraries. |

### Bundled native libraries need a compliance pass

The Snap recompiles FFmpeg from source as an LGPL build and ships the source
archive and notices (`snap/licenses/SOURCES.md`). The Windows bundle, and
therefore the MSIX, instead contains the libraries from the PyAV 18.1.1 Windows
wheel. That wheel carries `libx264-165.dll` and `libx265.dll` (GPL-licensed
encoders) beside FFmpeg, and the installer ships only the project `LICENSE`: no
third-party notices and no source offer. ParrotIA decodes audio and does not
need the encoders. Before the Store submission, and ideally for the existing
Windows installer too:

1. Check which FFmpeg license the PyAV Windows wheel's build reports.
2. Either build Windows with an LGPL-only FFmpeg, as the Snap does, or ship the
   license texts and an offer or copy of the corresponding source for each
   bundled GPL and LGPL library.
3. Add the notices file to the bundle and link it from the listing.

## Not yet verified

- Whether the AGPL-3.0 license is acceptable to you as an individual under the
  App Developer Agreement. The text does not forbid it (see the review above),
  but the indemnity in 10.c and the FOSS compliance duties are yours. No legal
  advice was taken.
- Where to host the privacy policy. The
  [privacy section of the signing policy](code-signing-policy.md#privacy-policy)
  is public, but a standalone privacy page is a better listing link.
- Whether `runFullTrust` needs a written justification at submission.
- The exact logo and screenshot sizes Partner Center wants. The source icon is
  256×256, which is enough for the package logos but probably too small for
  the larger listing artwork.
- Package size limits, and whether the Store accepts a package this large.
- Whether Partner Center accepts the unsigned package that `msix.py` produces. If
  it asks for a signature, sign with a self-signed certificate whose subject is
  exactly the publisher value above.
- Fee status in practice: Microsoft's pages describe no registration fee for
  individuals. If Partner Center asks for payment, stop and check.
