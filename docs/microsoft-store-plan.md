# Microsoft Store submission plan

Research date: **16 November 2026**. Checkout inspected: **ParrotIA 1.4.1**.

This plan covers publishing the Windows desktop app in the Microsoft Store. The Snap and Fedora work is tracked in [store-submission-plan.md](store-submission-plan.md).

## Development status (16 November 2026)

The owner chose to do all development work before creating the Partner Center account. Work packages 1–3 are implemented, using the recommended decisions: the MSIX route, and a model cache in the package's own `LocalCache` folder, which uninstall removes. Work packages 0 and 4 (account, name reservation, submission) remain.

**Implemented:**
- `src/parrotia/_msix.py` reads the package family name (`GetCurrentPackageFamilyName`).
  - When packaged and `HF_HOME`/`HF_HUB_CACHE` is unset, it sets `HF_HOME=%LOCALAPPDATA%\Packages\<family>\LocalCache\huggingface`.
  - It moves the Explorer queue to `...\LocalCache\explorer-queue`, so the Store and Inno builds never share a queue.
- `packaging/launcher.py` applies those defaults before any model library loads, and skips the custom AppUserModelID when packaged. The frozen smoke test now reports `packaged` and `hf_home`.
- `parrotia.app.main` preloads a file or folder passed on the command line, for **Open with**.
- `packaging/windows/msix.py`, driven by `build.py --msix` or run directly against `dist/ParrotIA`:
  - Renders `msix/AppxManifest.xml.in` from `msix/identity.json`, the version (`1.4.1` becomes `1.4.1.0`) and `SUPPORTED_EXTENSIONS`.
  - Draws 30 logo variants from `make_icon.draw_badge()`: scales 100–400, plus target sizes 16–256 in plated and unplated forms.
  - Indexes the logos in a single `resources.pri` (MakePri, with resource-package splitting removed) and packs the result with `MakeAppx /h SHA256`.
  - Also writes the 300×300 Store tile icon.
- **Manifest:**
  - `runFullTrust`.
  - One file-type association for all 21 media types, with `MultiSelectModel="Document"` for Open with.
  - A `Transcribe` verb ("Transcribe on Parrot", `--shell "%1"`, `MultiSelectModel="Player"`).
  - App execution alias `parrotia-app.exe`, which avoids clashing with pip's `parrotia`/`parrotia-gui`.
  - `MinVersion` 10.0.17763.0.
- `packaging/windows/test-msix.ps1` (elevated) does the following:
  - Test-signs a copy and trusts its certificate in `LocalMachine\TrustedPeople`.
  - Installs it and runs the frozen smoke test inside the package through the alias.
  - Checks package identity, and that the model cache is created in `%LOCALAPPDATA%\Packages\<family>\LocalCache\huggingface`.
  - Checks the ProgID verb for every extension.
  - With `-Wack`, runs WACK.
  - Removes the package and certificate, and fails if package data, the alias or the package is left behind.
- **CI:** `windows.yml` builds the MSIX, runs `test-msix.ps1` (adding `-Wack` when the runner has the kit) and uploads the unsigned `windows-msix` artifact, plus any WACK report.
  - The MSIX is **not** attached to GitHub releases. Windows refuses to install an unsigned package that contains executables (0x80073D2B), so the file is only useful for Partner Center.
- **Listing material:** `docs/PRIVACY.md` and `docs/microsoft-store-listing.md` (every Partner Center field, the IARC answers, the `runFullTrust` justification and the certification notes).

**Verified locally (Windows 11 25H2, not elevated):**
- 254 tests pass, and ruff passes.
- The real 1.4.1 bundle (280 MB) builds, passes the frozen smoke test, and packs to a 118 MB MSIX. MakeAppx schema-validated the manifest.
- A `makepri dump` shows all 30 logo candidates.

**First elevated run (owner, 16 November 2026):**
- The test-signed package installed, and the frozen app started inside it through the alias.
- The smoke test then failed to write its report into `Documents\ParrotIA\build\...`. Windows Security's **Controlled folder access**, which is on for this PC, blocked `parrotia-gui.exe`, and Python surfaced the denial as `FileNotFoundError` (errno 2).
- The failure in the error handler also raised PyInstaller's unhandled-exception dialog, which would hang CI.

**Fixes:**
- `test-msix.ps1` now writes the report into a fresh `%SystemDrive%\ParrotIA-msix-test-*` folder and stops the app after 3 minutes.
- The launcher never shows a dialog in smoke-test mode.
- The GUI, CLI and Explorer queue now report blocked saves as `OutputBlockedError`, naming the setting and the protected folders (`formats.write_output` / `blocked_write_error`). The README explains it.

**Impact on users:**
- Controlled folder access is off by default, and the problem is not specific to MSIX: the Inno build behaves the same.
- Users who enable it, or whose organization enforces it, cannot save transcripts beside media in Documents, Desktop, Pictures, Videos or Music until they allow ParrotIA or pick another output folder.
- Defender allows apps it considers "friendly" automatically. Whether the Microsoft-signed Store build gains that reputation is unverified; recheck after publication.

**Second elevated run (owner, 16 November 2026):**
- The install, the alias and the packaged smoke test passed. The report showed `packaged: true` and decoded audio.
- The redirection check failed. The model-cache folder was created in the **real** `%LOCALAPPDATA%\ParrotIA\huggingface`, because `%LOCALAPPDATA%\ParrotIA` already existed: the Inno build's Explorer queue had created it on 11 November. Windows does not redirect writes into a folder that already exists outside the package, so for anyone who used the Inno build first, models would have survived uninstall.
- **Fix:** the packaged app now writes directly to the package's `LocalCache`, which is never redirected and is always deleted on uninstall. The Explorer queue moved there too. The empty stray folder was removed.

**Third elevated run (owner, 16 November 2026): passed.** `test-msix.ps1 -Wack` reported "MSIX verified".
- It installed the package and ran the smoke test inside it.
- The model cache was created in the package's `LocalCache`.
- The `Transcribe` verb was registered for all 21 media types.
- Removal was clean.

**WACK overall: WARNING.** Warnings do not fail certification. There were two items:
- **Blocked executables** (an optional test, which flags code Windows 10 in S mode would refuse to launch):
  - Static references to `CreateProcess`/`ShellExecute` in `python312.dll`, `tcl86t.dll`, `libiomp5md.dll` and the PyInstaller bootloader, and the strings "cmd", "reg" and "csi" in `parrotia-gui.exe`.
  - ParrotIA launches none of these programs.
  - This is inherent to the Python, Tcl and OpenMP runtimes. No action needed.
- **DPIAwarenessValidation** (a warning): `parrotia-gui.exe` declares no PerMonitorV2 awareness in its manifest.
  - The app is DPI-aware at runtime, because CustomTkinter's scaling tracker calls `shcore.SetProcessDpiAwareness(2)` (per-monitor v1). WACK only inspects the manifest and static imports, so it can't see this.
  - CustomTkinter deliberately leaves the PerMonitorV2 call commented out. Forcing V2 through the PyInstaller manifest would change scaling for the Inno build too, so it is left as is.
  - Revisit only if Partner Center or a tester raises it.

**Still not verified:**
- Main-menu placement on Windows 11: needs a manual right-click check after installing with `test-msix.ps1 -KeepInstalled`.

**Windows 11 main context menu (16 November 2026):**
- The owner confirmed that the manifest `uap3:Verb` appears only under "Show more options".
- The package now ships `parrotia_shell.dll`, a native `IExplorerCommand` handler (`packaging/windows/shell/`), registered with `desktop4:FileExplorerContextMenus` (ItemType `*`) and a `com:SurrogateServer` class. The CLSID `A62953B0-E72C-49CD-B8AC-09742C34D586` is fixed.
- The handler hides itself unless the selection contains supported media.
- It starts the app with `--shell <files>` through `IApplicationActivationManager`, using the package's AppUserModelID derived from its install folder, so the app keeps its package identity. Selections longer than one command line are split across processes, which the Explorer queue merges.
- The `uap3:Verb` was removed to avoid a duplicate entry. The file association stays for "Open with".
- `MinVersion` rose to 10.0.19041.0, because packaged Explorer commands need 1903 or later.
- `msix.py` compiles the DLL with MSVC (`/W4 /WX`), found through vswhere and present on GitHub's Windows images.
- Every build runs `shell_test.exe`. It loads the DLL as Explorer does, then checks the title, the icon, hide/show, the quoted arguments, the split of long selections, and the AppUserModelID when installed.
- `test-msix.ps1` runs that test against the installed DLL, and also runs the smoke test through app activation.
- This applies only to the Store package: the Inno build has no package identity, so its verb stays under "Show more options".
- The Windows CI run of the same test (not pushed yet).
- Background notes: sideloading needs a certificate trusted machine-wide. An unsigned package is refused (0x80073D2B), a certificate trusted only per-user is refused too (0x800B0109), and `appcert.exe` requires elevation.

**When the account exists:**
1. Paste the Partner Center identity into `packaging/windows/msix/identity.json` and set `"placeholder": false`.
2. Rebuild, and upload `dist/msix/ParrotIA-<version>-windows-x64.msix`.

## Summary

- **Route:** submit an **MSIX package** built from the existing PyInstaller bundle. Do not submit the Inno Setup `.exe`.
  - With MSIX the Store signs the package for free, hosts it and delivers updates.
  - An MSI/EXE submission needs a paid code-signing certificate on every PE file, a self-hosted versioned URL, a silent installer, and its own update mechanism.
- **Account:** an Individual developer account is free under the new onboarding flow. It needs a personal Microsoft account and ID-plus-selfie verification.
- **Main engineering work:**
  - Rebuild the right-click "Transcribe on Parrot" entry as a manifest verb, because HKCU registry writes are virtualized inside MSIX.
  - Stop setting a custom AppUserModelID when packaged.
  - Decide where models are cached, so uninstall stays clean.
  - Add an MSIX build, local install test and WACK run to CI.
- **Compliance work:**
  - Publish a privacy policy. It is mandatory for every Win32/Desktop Bridge product, even one that collects nothing.
  - Disclose the Hugging Face download and its size at the start of the description.
  - Fill in the IARC age-rating questionnaire.
  - Supply AGPL license terms in place of Microsoft's standard terms.
  - Justify `runFullTrust`.
- **Timeline:** about 4–7 working days of engineering. Certification takes up to three business days, longer if desktop apps are reviewed manually.

## Verified requirements

### Account

Source: [Open a developer account](https://learn.microsoft.com/en-us/windows/apps/publish/partner-center/open-a-developer-account), updated 29 October 2026.

- "With the new onboarding experience, there are no registration fees for either account type." Start from the Store marketing site, [storedeveloper.microsoft.com](https://storedeveloper.microsoft.com/). Other entry points may still show the legacy flow.
- **Individual accounts:** the page says "Individual developer accounts must use a personal Microsoft account". Verification uses "a government-issued ID and selfie", captured on a phone.
  - Eligible: developers whose Store distribution is "not in relation to their business, trade, or profession", plus hobby and personal projects. A free open-source app published under the author's own name fits.
- **Company accounts:** need a registered business, a work (Entra ID) account and DUNS or business documents. They are not needed here.
- **No conversion:** "Changing a developer account from Individual to Company is not supported." A company account later means a new account and moving the app.
- **Brazil:** listed among the Store's developer [account locations](https://learn.microsoft.com/windows/uwp/publish/account-types-locations-and-fees). That page is older; confirm during sign-up.
- **Name reservation:** the app name can be reserved before the package exists. A package must be submitted within **three months**, or the reservation lapses.

### MSIX vs MSI/EXE

Sources: [MSIX package requirements](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/app-package-requirements), [MSI/EXE package requirements](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msi/app-package-requirements) (both updated 24 August 2026), and [Choose a distribution path](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/choose-distribution-path) (7 October 2026).

| | MSIX (proposed) | MSI/EXE (Inno Setup installer) |
| --- | --- | --- |
| Signing | "The Microsoft Store will automatically re-sign your MSIX/AppX packages". No certificate is needed. | The installer **and every PE file** must chain to a Microsoft Trusted Root Program CA. Self-signed is rejected, and the Store does not re-sign. |
| Hosting | Store CDN | A versioned HTTPS URL you host. The binary behind it must never change. |
| Updates | Store-managed, differential, staged rollout | "Updates are the app's responsibility." |
| Installer | Not applicable | Silent install, standalone and offline, no bundled software (policy 10.2.9) |
| Version | `Major.Minor.Build.0`. The fourth field is reserved and must be 0. | Managed by the installer |
| Size | 25 GB per package | Not a concern |

A PyInstaller bundle has hundreds of PE files (Python, ctranslate2, onnxruntime, av), and all of them would need signing on the MSI/EXE route. This plan did not check Microsoft's own signing service (Azure Artifact Signing) for individual developers in Brazil, and the MSI/EXE page does not mention that service. MSIX avoids the question entirely.

### Store Policies (version 7.20, in effect since 22 October 2026)

Source: [Microsoft Store Policies](https://learn.microsoft.com/en-us/windows/apps/publish/store-policies). These sections apply to ParrotIA:

- **10.1 / 10.1.1:** the metadata must describe "any important limitations of your product". "The value proposition of your product must be clear during the first run experience."
  - The model download (a few hundred MB to about 1.5 GB) and a CPU-only baseline count as important limitations.
- **10.2.2:** "Your product must not attempt to fundamentally change or extend its described functionality … through any form of dynamic inclusion of code."
  - Whisper weights are data loaded by CTranslate2, not executed code. ParrotIA downloads no scripts or plugins.
- **10.2.4:** "Your product may depend on non-integrated software (such as another product, module, or service) to deliver its primary functionality if you disclose the dependency at the beginning of the description".
  - The Hugging Face model download goes in the **first lines** of the description.
- **10.2.7:** "Your product must clearly communicate and enable a user's ability to cleanly uninstall and remove your product". This bears on the model cache; see work package 2.
- **10.3:** the product must be testable. There are no accounts. The certification notes should tell testers to choose a small model.
- **10.5.1:** "Product types that inherently have access to Personal Information must always have privacy policies. These include, but are not limited to, Desktop Bridge and Win32 products."
  - **A privacy policy URL is mandatory.**
- **11.11:** an IARC age rating, kept accurate for the product's lifetime.
- **11.16 Live Generative AI Content:** covers products with "dynamic content created by generative AI models in response to user inputs". Requirements: disclose it in the metadata and in Partner Center, keep the output policy-compliant, and give users a way to report content. The last requirement was reported in the fetched summary but not seen verbatim.
  - Speech-to-text arguably falls outside this policy, but Whisper is a generative sequence-to-sequence model. See the open decisions.

### MSIX behavior that affects ParrotIA

Sources: [Prepare to package a desktop app](https://learn.microsoft.com/en-us/windows/msix/desktop/desktop-to-uwp-prepare), [Behind the scenes](https://learn.microsoft.com/en-us/windows/msix/desktop/desktop-to-uwp-behind-the-scenes), [Integrate with File Explorer](https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/integrate-packaged-app-with-file-explorer) and [Desktop extensions](https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/desktop-to-uwp-extensions).

| Current behavior (observed) | Inside MSIX | Action |
| --- | --- | --- |
| `packaging/launcher.py` calls `SetCurrentProcessExplicitAppUserModelID("ParrotIA.Desktop")` | "You can't define custom AUMIDs"; "Do not programmatically set your AppID in code" | Skip the call when packaged |
| `build.py` writes `HKCU\Software\Classes\SystemFileAssociations\<ext>\shell\ParrotIA.Transcribe` | "All writes under HKCU are copied on write to a private per-user, per-app location". Explorer will not see the verbs. | Declare a `uap3:Verb` under a `windows.fileTypeAssociation` extension |
| Explorer queue in `%LOCALAPPDATA%\ParrotIA\explorer-queue` (`explorer.py:285`) | New AppData files are redirected to per-package storage, but **not** when the folder already exists outside the package (observed on 16 November 2026). | Done: when packaged, the queue lives in the package's `LocalCache` |
| faster-whisper models in `%USERPROFILE%\.cache\huggingface` (huggingface_hub default) | Not redirected: it is a real write, and it **survives uninstall** | Decide the cache location (work package 2) |
| Outputs beside the input file | Allowed when the user has permission | No change |
| Install directory | Read-only (`WindowsApps`) | ParrotIA already writes nothing there; keep it that way |

**Verb facts:**
- `MultiSelectModel="Player"` passes every selected file to one process. `parrotia.explorer.main` already accepts `nargs="+"`.
- `Parameters` takes `"%1"`.
- A file type association also lists the app under **Open with** for those types. Launching through Open with currently opens an empty GUI.
- A true Windows 11 top-level menu entry needs `desktop4:FileExplorerContextMenus` with a native C++ `IExplorerCommand` COM DLL. Plain `uap3:Verb` entries appear only under "Show more options" (confirmed 16 November 2026), so the package now uses an `IExplorerCommand` handler.

### Submission and certification

Sources: [Create an app submission](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/create-app-submission), [certification process](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/app-certification-process), [screenshots and images](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/screenshots-and-images), [age ratings](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/age-ratings), [store listing](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/add-and-edit-store-listing-info), [submission options](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/manage-submission-options), [license terms field](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/add-additional-information).

Partner Center submission sections:

1. **Pricing and availability:** markets, discoverability, schedule and price (Free).
2. **Properties:** category, the privacy policy URL, website and support contact.
3. **Age ratings:** the IARC questionnaire. "Save and generate" produces the rating, which carries over to later updates.
4. **Packages:** the `.msix`.
5. **Store listings:** at least one language.
   - Description: required, up to 10,000 characters, plain text, no URLs.
   - Up to 20 features, a short description, and "Additional license terms" (a URL or up to 10,000 characters). Leaving that field blank applies the Standard Application License Terms.
   - Screenshots: at least 1 and up to 10, PNG, 1366×768 or larger, without overlaid logos.
   - A 300×300 tile icon is strongly recommended.
6. **Submission options:**
   - Restricted-capability justification, required because the package declares `runFullTrust`. Community answers say "a Win32 app packaged as MSIX" is a sufficient reason; the current official wording was not found.
   - Notes for certification.
   - Publishing hold.

**Certification** runs a malware scan, the Windows App Certification Kit (WACK) and a content review. It "can take up to three business days". A failure returns a report, and the fix goes in a new submission. Every update is also a new submission.

**Automation:** the [Microsoft Store Developer CLI](https://learn.microsoft.com/en-us/windows/apps/publish/msstore-dev-cli/overview) (preview) publishes updates with `msstore publish -i <file>.msix` and runs on GitHub Actions through `microsoft/microsoft-store-apppublisher`.
- It cannot create the first submission.
- It needs an **Entra ID tenant linked to Partner Center**, plus a tenant ID, seller ID, client ID and secret. Sign-in with a personal Microsoft account is rejected.
- Whether an Individual account can link a tenant is unverified.

## Roadmap

### Work package 0: account and identity (owner, about 1 day plus verification wait)

1. Sign up at storedeveloper.microsoft.com as an **Individual** with the personal Microsoft account. Complete the ID and selfie verification.
2. Read the App Developer Agreement as presented. Check its open-source (FOSS) clause, which is reported to allow terms an OSI license requires.
3. Reserve the name **ParrotIA**. The three-month submission window starts now, so reserve only once work packages 1–3 are near done. Note fallback names.
4. Copy the identity values from *Product management → Product identity*: `Package/Identity/Name`, `Package/Identity/Publisher` (`CN=…`) and `PublisherDisplayName`. They are case-sensitive and not secret, so they can be committed to the build config.

### Work package 1: packaged-mode app changes (developer, about 1–2 days)

1. Add a private helper that detects package identity, using `GetCurrentPackageFullName`, which returns `APPMODEL_ERROR_NO_PACKAGE` (15700) when the app is not packaged.
2. `launcher.py`: skip `SetCurrentProcessExplicitAppUserModelID` when packaged.
3. GUI: accept file paths on the command line and preload them, so **Open with → ParrotIA** works. Both the GUI and `parrotia-gui.exe` paths need it.
4. Model cache: when packaged and `HF_HOME`/`HF_HUB_CACHE` is unset, point `HF_HOME` at `%LOCALAPPDATA%\Packages\<family>\LocalCache\huggingface` before faster-whisper is imported.
   - Windows deletes that folder on uninstall, which satisfies 10.2.7.
   - Don't rely on AppData redirection: it doesn't apply when the folder already exists outside the package.
   - Users of both the Inno and Store builds would download models twice.
5. Tests: unit-test the detector, the AUMID branch, the cache default (unset and preset) and the GUI's argv handling, with the Windows API mocked.

### Work package 2: MSIX build (developer, about 2 days)

1. Add `packaging/windows/msix/AppxManifest.xml.in`, rendered by `build.py --msix` from `__version__` (`1.4.1` → `1.4.1.0`) and the identity values:
   - `TargetDeviceFamily Windows.Desktop`: `MinVersion 10.0.17763.0`, the Inno minimum, and `MaxVersionTested` set to the newest Windows build tested.
   - `<Application Executable="parrotia-gui.exe" EntryPoint="Windows.FullTrustApplication">`. Add an app execution alias (`parrotia-app.exe`) so the packaged smoke test can be started from a shell.
   - `rescap:runFullTrust`.
   - One `uap:FileTypeAssociation` for `SUPPORTED_EXTENSIONS`, generated from the same list as `registry_entries()`, with `uap3:Verb Id="Transcribe" MultiSelectModel="Player" Parameters="--shell &quot;%1&quot;"`. The display text is "Transcribe on Parrot".
   - Languages: `en-us`.
2. Generate the visual assets from `assets/parrotia.png` with Pillow, extending `make_icon.py`:
   - `Square44x44Logo` with `targetsize-16/24/32/48/256` and `altform-unplated` variants (the taskbar uses them)
   - `Square150x150Logo`, `Wide310x150Logo` and `StoreLogo` (50×50), at scale-100 and scale-200
3. Pack the existing `dist/ParrotIA` layout with `MakeAppx.exe pack /h SHA256`, from the Windows SDK on the `windows-latest` runner. Microsoft's `winapp` CLI is in preview, so don't depend on it.
4. Add `packaging/windows/test-msix.ps1`:
   - Sign a copy with a throwaway self-signed certificate whose subject equals the Publisher.
   - `Add-AppxPackage`, then run the frozen `--smoke-test` through the alias.
   - Check the verbs and the file-type registration, then `Remove-AppxPackage`. Confirm nothing is left in redirected AppData.
5. Run WACK (`appcert.exe`, elevated) and keep the report. Check whether the runner image includes the kit; otherwise run it locally.
6. CI: build and test the MSIX in `windows.yml`, and upload the unsigned `.msix` as an artifact. Don't attach it to GitHub releases: users can't install an unsigned package.
7. Manual QA on Windows 10 22H2 and Windows 11:
   - Install, first-run model download and a real transcription
   - Right-click a single file and a multi-file selection, and Open with
   - Taskbar icon and grouping
   - Update to a higher version, then uninstall
   - Side by side with the Inno install (duplicate verbs are expected)

### Work package 3: listing and compliance material (developer and owner, about 1 day)

1. **Privacy policy:** add `docs/PRIVACY.md` and link its GitHub URL in Partner Center. State:
   - No accounts, no telemetry, and audio processed locally.
   - Model downloads go to Hugging Face, which sees the IP address under its own privacy policy.
   - The cache location and the output locations.
   - What uninstall removes.
2. **Description:**
   - Open with the dependency and limitation disclosure, for example: *"Speech models (a few hundred MB to about 1.5 GB) are downloaded once from Hugging Face on first use, then work offline."*
   - Then the features. Keep CPU as the advertised baseline; GPU via CUDA is not tested in this package.
   - Write up to 20 feature bullets and a short description of 270 characters or fewer.
3. **Screenshots:** four to six PNGs at 1920×1080, captured on Windows from the MSIX build. Show the main window, a finished transcript, the format choices and the right-click verb.
4. **Additional license terms:** link the AGPL-3.0 `LICENSE` and the release's corresponding-source URL. AGPL §6 requires source access for object-code distribution, and the Standard Application License Terms don't fit.
5. **Properties:** category Productivity or Utilities & tools; website = the GitHub repository; support = the GitHub issues page.
6. **IARC:** answer as a utility: no user interaction or sharing, no purchases. A minimal rating is expected.
7. **Certification notes:** no sign-in is needed. Choose the `tiny` or `base` model for a quick test (a few tens of MB to roughly 150 MB). Mention a sample-audio link, and that the right-click verb appears for audio and video files.
8. **runFullTrust justification:** "ParrotIA is a Win32 desktop application (Python/Tk) packaged as MSIX; full trust is required to run its executable and native inference libraries."

### Work package 4: submit, certify, publish (owner, about 3–5 business days elapsed)

1. Create the first submission in Partner Center. Make the first release available but not discoverable, or set a publishing hold, so it can be installed from the Store on a clean machine first.
2. Answer any certification report and resubmit as needed.
3. After the clean-machine install, transcription and uninstall checks pass, make the app discoverable in all markets.
4. Add the Store badge and link to the README. Record the Store ID and status in this document.

### Work package 5: maintenance and automation (later)

- **Releases:** each release makes a new submission with a higher `x.y.z.0`. Manual upload works without extra setup.
- **CI publishing:** if an Entra tenant can be linked to the Individual account, add `msstore publish` to `release.yml` with the four secrets, using `--noCommit` until it is trusted.
- **Keep the Inno installer** on GitHub releases for users without Store access.
- **winget:** Store MSIX apps are also installable through winget's `msstore` source. A separate `winget-pkgs` manifest for the Inno installer is optional.
- **Later:** an `IExplorerCommand` handler for a Windows 11 top-level menu entry, if users ask for it.

## Open decisions for the owner

1. **Route:** MSIX (recommended) or the signed Inno `.exe`.
2. **Model cache when packaged:** `%LOCALAPPDATA%` (recommended; clean uninstall, but no sharing with the Inno build) or `%USERPROFILE%\.cache\huggingface`, which keeps working after uninstall but must be disclosed as left behind.
3. **Policy 11.16:** if Partner Center asks about generative AI, answer conservatively and disclose it. GitHub issues already serves as the reporting channel. The alternative is to argue that speech recognition falls outside "dynamic content created … in response to user inputs".
4. **Category:** Productivity or Utilities & tools.

## Not verified

- Brazil eligibility and the exact publisher-display-name rules for individual accounts. The onboarding page renders only in a browser; confirm during sign-up.
- Whether `runFullTrust` approval still needs manual justification, and how long manual desktop-app reviews take today.
- The App Developer Agreement's exact FOSS wording.
- Where `uap3:Verb` entries appear in the Windows 11 context menu.
- Whether the GitHub `windows-latest` image ships WACK.
- Whether an Individual account can link an Entra tenant for `msstore`.
