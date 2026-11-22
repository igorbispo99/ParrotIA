# Microsoft Store roadmap

[Documentation](README.md) · [Distribution channels](distribution-channels.md) · [Code signing setup](code-signing.md)

Prepared **22 November 2026** against ParrotIA **1.5.3**. Status: the product
name **ParrotIA** is reserved in Partner Center (22 November 2026, kept for three
months unless a submission is made), a test MSIX builds, installs and passes the
app's smoke test under package identity in CI, and nothing has been uploaded or
submitted yet.

Publishing as MSIX removes the need for a code signing certificate: after
certification the Store re-signs the package with a Microsoft certificate.
Submitting the existing Inno Setup `.exe` instead would require the project's
own trusted signature, so it is not the plan. The Store would add a search
listing and automatic updates, and a Microsoft-signed package avoids the
unsigned-installer warning. It does not replace the direct download.

## Reserved product

| Field | Value |
| --- | --- |
| Product | ParrotIA (MSIX or PWA app), status *draft* |
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
| 1 | Register a Partner Center account (**done**) | Project owner | Individual accounts have no registration fee under the new flow. Start at [storedeveloper.microsoft.com](https://storedeveloper.microsoft.com), sign in with a personal Microsoft account, then verify with a government ID and a selfie taken on a phone. The country cannot be changed later and an individual account cannot become a company account. Verification time is not published. |
| 2 | Reserve the product name (**done**: ParrotIA) | Project owner | Partner Center → New product → MSIX → check availability. A reservation lasts three months. Copy the *Product identity* values (Name, Publisher, Publisher display name). |
| 3 | Build the submission package | Developer | `python packaging/windows/msix.py --identity-name … --publisher … --publisher-display-name …` with the Partner Center values. The version is `major.minor.patch.0`; the Store reserves the last part. |
| 4 | Test the package | Developer | Run the workflow, then install on a real Windows 10/11 machine and exercise a full transcription (model download, folder input, export beside the source). |
| 5 | Complete the listing | Project owner | Pricing (free), properties, age rating (IARC questionnaire), packages, description, screenshots and logos, and notes for certification. |
| 6 | Submit and respond | Project owner | Certification is documented as taking up to three business days, with the listing visible about 15 minutes after approval. |

## Behaviour that changes in a packaged app

- **Model cache is removed on uninstall.** The app keeps models in
  `%LOCALAPPDATA%\ParrotIA`. For packaged apps, new files under `LocalAppData`
  are redirected to a private per-package location, and uninstalling deletes
  redirected files. The roughly 1.6 GB default model would be downloaded again
  after a reinstall, whereas the Inno installer keeps it. Either explain this in
  the listing or store the cache where it survives (a user-chosen folder), which
  needs a code change.
- **No Explorer right-click action in the first Store edition.** The action is a
  per-user registry entry created by the Inno installer. A packaged app would
  need a different mechanism (a registered Explorer command component).
- **The install folder is read-only.** The app must not write next to its own
  executable. Outputs beside a user's input file are documented as allowed when
  the user has permission; confirm on the packaged build.
- **`runFullTrust` is a restricted capability.** The package requests only this
  one. Prepare a short justification: a desktop application that reads and writes
  user-selected audio, video and transcript files.

## Not yet verified

- Whether the AGPL-3.0 license and the Microsoft Store App Developer Agreement
  and Store Policies are compatible. This is the same kind of question as the
  [Mac App Store license review](mac-app-store-roadmap.md) and has not been
  checked. Do not submit until it is resolved.
- Whether certification requires a privacy policy URL for an app that accesses
  the internet (it downloads models). Plan to provide the
  [privacy section of the signing policy](code-signing-policy.md#privacy-policy)
  once it is public.
- Whether the justification for `runFullTrust` is required, and its wording.
- The exact logo and screenshot sizes Partner Center wants. The source icon is
  256×256, which is enough for the package logos but probably too small for
  the larger listing artwork.
- Package size limits, and whether the Store accepts a package this large.
- Fee status in practice: Microsoft's pages describe no registration fee for
  individuals, but some older pages still mention a one-time charge. If
  Partner Center asks for payment, stop and check.
