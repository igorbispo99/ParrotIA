# Code signing setup (maintainers)

[Documentation](README.md) · [Public code signing policy](code-signing-policy.md) · [Building installers](building.md)

Release workflows can sign the Windows and macOS installers, but **no signing
account exists yet and none of this has run against a real certificate**. Until
the secrets below are configured, every workflow produces the same unsigned
artifacts as before. Signing is attempted only for `v*` tags, never for pull
requests, forks or ordinary pushes.

## What the workflows do

| Platform | Release-tag run, once configured |
| --- | --- |
| Windows | Builds the app, submits `parrotia-gui.exe` to SignPath, re-runs the frozen-app smoke test on the signed file, compiles the installer, submits `*-setup.exe` to SignPath, checks both signatures with `Get-AuthenticodeSignature`, then runs the installer test. |
| macOS | Imports a Developer ID certificate into a temporary keychain, signs every Mach-O file in the bundle (hardened runtime, secure timestamp), signs and notarizes the DMG, staples the ticket and checks Gatekeeper acceptance, then deletes the keychain. |

Without configuration both jobs log that signing is not enabled and continue.

## Windows: SignPath Foundation

**Status as of 22 November 2026.** The Foundation declined the 21 November
application because ParrotIA has too little public evidence of community
adoption. It welcomes a new application once the project can point to broader
use, independent coverage or sustained contributor activity. SignPath also
offered a [paid subscription](https://docs.signpath.io/change-subscription).
The direct Windows installer remains unsigned. The [Microsoft Store MSIX
submission](microsoft-store-roadmap.md) was published on 23 November 2026.

SignPath Foundation offers free certificates to open source projects. The
[conditions](https://signpath.org/terms) include an OSI-approved license without
commercial dual licensing, no proprietary components, active maintenance, a
release already published in the form to be signed, multi-factor authentication
for all team members, a code signing policy on the project pages, and manual
approval of each signing request. The certificate is issued to SignPath
Foundation, which becomes the publisher shown by Windows. Acceptance is at
their discretion.

1. Turn on two-factor authentication for the GitHub account.
2. When broader adoption is documented, reapply at [signpath.org](https://signpath.org) with the repository URL and the
   [code signing policy](code-signing-policy.md). Say that the installer bundles
   upstream Python, FFmpeg/PyAV, ONNX Runtime and CTranslate2 binaries, and ask
   whether they may stay unsigned inside the signed installer. The NVIDIA CUDA
   libraries are **not** bundled; they are an optional `parrotia[cuda]` extra.
3. After approval, in the SignPath project, create the two artifact configurations below, a
   signing policy named `release-signing` that requires manual approval, and
   an API token for the CI user. Install the SignPath GitHub app if prompted.
4. In the GitHub repository, add:

| Kind | Name | Value |
| --- | --- | --- |
| Secret | `SIGNPATH_API_TOKEN` | API token of the SignPath CI user |
| Variable | `SIGNPATH_ORGANIZATION_ID` | Organization ID shown in SignPath |
| Variable (optional) | `SIGNPATH_PROJECT_SLUG` | Defaults to `ParrotIA` |
| Variable (optional) | `SIGNPATH_SIGNING_POLICY_SLUG` | Defaults to `release-signing` |
| Variable (optional) | `SIGNPATH_APP_CONFIGURATION_SLUG` | Defaults to `app-exe` |
| Variable (optional) | `SIGNPATH_INSTALLER_CONFIGURATION_SLUG` | Defaults to `installer-exe` |

Artifact configurations, written from SignPath's
[syntax reference](https://docs.signpath.io/artifact-configuration/syntax).
`actions/upload-artifact` wraps each file in a ZIP, hence the `zip-file` root.
Check them against the documentation in the SignPath editor before the first run;
the metadata values must match the version resources that `build.py` writes
(`ProductName` `ParrotIA`, `ProductVersion` equal to the package version).

`app-exe`:

```xml
<artifact-configuration xmlns="http://signpath.io/artifact-configuration/v1">
  <parameters>
    <parameter name="version" required="true" />
  </parameters>
  <zip-file>
    <pe-file path="parrotia-gui.exe" product-name="ParrotIA" product-version="${version}">
      <authenticode-sign />
    </pe-file>
  </zip-file>
</artifact-configuration>
```

`installer-exe`:

```xml
<artifact-configuration xmlns="http://signpath.io/artifact-configuration/v1">
  <parameters>
    <parameter name="version" required="true" />
  </parameters>
  <zip-file>
    <pe-file path="*-setup.exe" product-name="ParrotIA" product-version="${version}">
      <authenticode-sign />
    </pe-file>
  </zip-file>
</artifact-configuration>
```

The workflow uses `signpath/github-action-submit-signing-request@v3`, the major
version shown in SignPath's documentation; confirm it is still current. The
action needs GitHub-hosted runners for open source projects, which these jobs use.

## macOS: Developer ID and notarization

Requires an [Apple Developer Program](https://developer.apple.com/programs/)
membership (US$99 a year at the time of writing).

1. In your Apple developer account create a **Developer ID Application**
   certificate, import it into Keychain Access, and export it with its private
   key as a `.p12` file protected by a password.
2. In App Store Connect create an API key (**Users and Access → Integrations →
   App Store Connect API**) with the Developer role, and note its Key ID and
   Issuer ID. Download the `.p8` file once; Apple does not show it again.
3. Add these repository secrets:

```bash
base64 -i DeveloperID.p12 | gh secret set APPLE_CERTIFICATE_P12
gh secret set APPLE_CERTIFICATE_PASSWORD
gh secret set APPLE_NOTARY_KEY < AuthKey_XXXXXXXXXX.p8
gh secret set APPLE_NOTARY_KEY_ID
gh secret set APPLE_NOTARY_ISSUER_ID
```

Run `gh secret set` from a trusted terminal and delete the `.p12` and `.p8`
files afterwards, or keep them in a password manager. Never commit them.

The macOS spec passes the signing identity to both `EXE` and `COLLECT`. PyInstaller's
`BUNDLE` inherits its settings from `COLLECT`, so before this change a signed
build would have signed only the launcher and notarization would have failed.
`build.py` also sets `PYINSTALLER_STRICT_BUNDLE_CODESIGN_ERROR` so a signing
failure stops the build and runs `codesign --verify --deep --strict` on the app.

To test locally with your own certificate and a stored notary profile, see
[Building installers](building.md#build-the-macos-app).

## Verify a signed release

Windows (PowerShell):

```powershell
Get-AuthenticodeSignature .\ParrotIA-<version>-windows-x64-setup.exe | Format-List Status, SignerCertificate
```

macOS:

```bash
codesign --verify --deep --strict --verbose=2 /Volumes/ParrotIA/ParrotIA.app
xcrun stapler validate ParrotIA-<version>-macos-arm64.dmg
spctl --assess --type open --context context:primary-signature -v ParrotIA-<version>-macos-arm64.dmg
```

Windows SmartScreen builds reputation from downloads, so a first signed release
can still show a warning for a short time.

## After the first signed release

- Edit the status paragraph at the top of the [signing policy](code-signing-policy.md)
  and add its link to the release notes and download pages, as SignPath requires.
- The installer hash changes with signing, so submit a new WinGet version rather
  than editing the existing manifest.
- For an official Homebrew cask, follow the [macOS roadmap](mac-app-store-roadmap.md).
- Re-check `brew audit --cask --online` before proposing the cask.

## Not yet verified

- The artifact configurations above still need to be checked with SignPath's validator.
- The Windows workflow was not run on a Windows runner after the build was split
  into `--bundle-only` and `--installer-only`; the unsigned path should be
  confirmed by a normal CI run on a branch before tagging a release.
- No Apple account, certificate or notarization has been exercised.
