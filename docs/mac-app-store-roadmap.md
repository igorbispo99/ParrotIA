# Mac App Store launch roadmap

[Documentation](README.md) · [Installer builds](building.md)

Prepared **17 November 2026**, against ParrotIA **1.5.3**. Status: planning;
no App Store candidate has been built, uploaded, or approved.

The goal is a free Mac App Store edition with local transcription, Metal on
Apple Silicon, file/folder input, all existing export formats, and predictable
cancellation and shutdown. Keep GitHub/Homebrew distribution available.
Free pricing, no accounts, and no in-app purchases are the proposed first-launch
scope; the owner can change these before implementation.

## Starting point

| Area | Current evidence | Work needed |
| --- | --- | --- |
| Trust | Homebrew-installed 1.5.3 has an ad-hoc signature and triggers Gatekeeper | Developer ID signing/notarization for direct downloads; separate Store signing |
| Packaging | PyInstaller app and architecture-specific DMGs; optional signing/notary flags in `packaging/macos/build.py` | Store distribution target, provisioning, build numbers, validation and upload |
| Sandbox | `packaging/macos/entitlements.plist` only disables library validation | Least-privilege Store entitlements and real sandbox testing |
| Inference | Bundled whisper.cpp, Metal, persistent spawned Python worker | Prove signed worker, IPC, native libraries, and selected-file access inside sandbox |
| Files | Tk dialogs; default exports beside input | Explicit permissions for input folders and writable export destinations |
| Models | Pinned, checksum-verified downloads; per-user Application Support cache | Container-aware storage, consent, disk-space handling and review explanation |
| Licensing | Project declares `AGPL-3.0-or-later`; bundled Python/native dependencies | Ownership, Store-term compatibility, codecs, model and notice audit |
| Reliability | 1.5.3 checks complete and active-quit transcription on ARM/Intel | Repeat against the actual sandboxed Store artifact and TestFlight install |

## Milestones and release gates

Estimates below are engineering effort for one maintainer, **not launch dates**.
Account verification, rights clearance and Apple review are additional elapsed
time. Re-estimate after the feasibility milestone.

| Milestone | Owner | Estimated effort | Exit evidence |
| --- | --- | --- | --- |
| 0. Account and distribution rights | Project owner; licensing reviewer | 2–4 days for inventory; clearance duration unknown | Active developer account and documented lawful Store distribution route |
| 1. Sandbox feasibility | Developer | 3–5 days | Signed prototype imports, transcribes with Metal, exports and quits under sandbox |
| 2. Signing for direct downloads | Developer + account owner | 1–3 days | Fresh Homebrew/DMG installation opens with normal Gatekeeper settings |
| 3. Store candidate | Developer | 5–10 days | Reproducible, validated candidate with permissions, models and lifecycle QA |
| 4. TestFlight and listing | Developer + owner/testers | 3–5 days plus beta feedback | Installed beta passes matrix; accurate listing/privacy/support materials |
| 5. Review and launch | Account owner + developer | 1–2 days preparation plus review | Approved version publicly installs and transcribes on a clean Mac |

Suggested order: start account setup and rights audit immediately; run the
sandbox prototype while those proceed. Direct-download signing can proceed
independently of Store acceptance. Fund the full Store implementation only
after milestones 0 and 1 pass. Budget roughly **3–6 engineering weeks** if the
current stack works; a native frontend/helper redesign changes that estimate.

## 0. Establish the account and distribution rights

- [ ] Enroll in or verify an Apple Developer Program membership. Decide individual
  versus organization enrollment and the public seller identity. Apple currently
  lists **US$99/year**, with regional pricing; enrollment/payment belongs to the
  account owner. [Enrollment](https://developer.apple.com/help/account/membership/program-enrollment/)
- [ ] Confirm control of `io.github.igorbispo99.ParrotIA`, register the App ID,
  and create the macOS app record in App Store Connect. Check the display name's
  availability before preparing listing assets.
- [ ] Inventory copyrights and contributions before proposing a license change.
  AGPL distribution needs a specific compatibility assessment against current
  Apple agreements and usage terms. Do not assume publishing source resolves it.
  The FSF documents historical GPL/App Store conflicts; that is a reason for
  review, not a current legal conclusion about this project.
  [FSF background](https://www.fsf.org/blogs/licensing/more-about-the-app-store-gpl-enforcement)
- [ ] Record a distribution route: confirm current terms work, obtain necessary
  permissions/exception, or dual-license an edition where all relevant rights
  permit it. Owner-written code cannot grant exceptions for dependencies.
  Keep the existing license unchanged until this decision is explicit.
- [ ] Inventory the **actual macOS payload**, including Python, Tk, CustomTkinter,
  fonts, Pillow, pywhispercpp/whisper.cpp, PyAV/FFmpeg, certificates and model/VAD
  weights. Record versions, licenses, notices, source/relinking obligations and
  codec build flags; resolve any GPL/LGPL or patent questions for that payload.

Gate: recorded rights assessment and required permissions, plus usable team
access. Unresolved Store rights block submission, not the existing OSS channel.

## 1. Prove sandbox feasibility before redesigning the UI

Apple requires appropriate sandboxing and a self-contained app for the Mac App
Store. The present entitlements do not implement this.
[Review requirements, 2.4.5](https://developer.apple.com/app-store/review/guidelines/#hardware-compatibility)

- [ ] Make a small Store build target with App Sandbox, outbound network access
  for models, and user-selected file access. Add only capabilities demonstrated
  necessary; file transcription does not require microphone or network-server access.
- [ ] Test Tk open/save/folder panels with actual sandbox permissions. Add a
  Cocoa bridge for scoped URLs/bookmarks if required; a selected path string
  alone is not proof the worker can access it. Balance scoped access lifetimes,
  refresh stale bookmarks, and handle revoked permissions.
  [Persistent file access](https://developer.apple.com/documentation/foundation/nsurl/)
- [ ] Prove `multiprocessing` spawn, resource tracking, Pipe/Event IPC, media
  decoding and Metal inference with final-style signing. Parent and helper
  entitlement layouts need separate validation; the existing same-executable
  relaunch may need a dedicated bundled helper. Apple's inheritance guidance
  specifies `app-sandbox` and `inherit` for an inheriting child target.
  [Sandbox inheritance](https://developer.apple.com/library/archive/documentation/Miscellaneous/Reference/EntitlementKeyReference/Chapters/EnablingAppSandbox.html)
- [ ] Validate all embedded native libraries, Python imports, Metal resources
  and Tk/font behavior without writes to the signed bundle or shared locations.
  Audit whether library-validation exceptions are needed and acceptable.
- [ ] Capture sandbox denials and a real transcription/active-quit report on a
  clean user account. Mocked tests cannot establish this gate.

Keep the existing frontend if this passes. If Tk/file access is the obstacle,
prototype native panels first. If worker signing/IPC is the obstacle, prototype
a dedicated helper or XPC service. Consider SwiftUI/AppKit only after recording
the failing constraint and comparing the maintenance cost; a rewrite is not
an assumed App Store requirement.

## 2. Fix trust for existing Homebrew and DMG users

- [ ] Use the existing build flags with a Developer ID Application identity,
  hardened runtime, complete nested signing and notarization. Verify the
  stapled download with signature and Gatekeeper checks.
- [ ] Put credentials in protected CI secrets/temporary keychains; never commit
  signing keys. Keep signing and publishing limited to trusted release jobs.
- [ ] Test a freshly downloaded ARM and Intel DMG on a clean account, with
  quarantine intact. No manual `xattr` step should be needed for acceptance.
- [ ] Publish new signed artifacts under a new release version, then update cask
  checksums. Preserve the existing release artifacts and tags.

This addresses the observed warning while Store work proceeds. Developer ID
notarization is for direct distribution; Store submission has its own security
checks and signing workflow.
[Apple notarization guidance](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution/)

## 3. Build the Store edition

- [ ] Add a separate Store target/pipeline, provisioning and distribution signing
  for app and embedded code, a monotonically increasing `CFBundleVersion`, and
  Xcode-supported packaging and validation. Upload through Xcode/Transporter;
  the current DMG is not the submission artifact. Recheck Apple's current
  Xcode/SDK upload requirements at implementation time.
  [Submission](https://developer.apple.com/app-store/submitting/) ·
  [Upload builds](https://developer.apple.com/help/app-store-connect/manage-builds/upload-builds/)
- [ ] Decide architecture coverage after the prototype: preferably one validated
  universal app; otherwise explicitly scope the first Store edition to Apple
  Silicon. Current separate DMGs do not establish universal dependency support.
- [ ] Use platform container-aware directories for persistent models and temporary
  downloads. Keep completed models durable for offline use and expose removal
  and disk usage. Import an existing Homebrew cache only through user-granted
  folder access; verify hashes and account for temporary duplicate disk usage.
- [ ] Make choosing a writable output folder explicit. Reading an input file must
  not imply permission to create sibling exports. Cover folder batches, external
  disks, iCloud files, read-only sources and restored access after relaunch.
- [ ] Show model size/storage/network requirements before downloading. Support
  cancel/resume, insufficient space, failed checksums and interrupted downloads.
  Offer a small first-run model; retain optional larger models after feasibility QA.
- [ ] Keep Python, libraries and inference code in the signed bundle. Explain to
  review that downloaded weights are data used by the submitted transcription
  feature; do not assume this guarantees acceptance. Review model delivery under
  rules 2.4.5(iv) and 2.5.2; if challenged, evaluate bundling the initial model.
  [Review guidelines](https://developer.apple.com/app-store/review/guidelines/)
- [ ] Use the Store for Store-edition updates. Keep Homebrew maintenance and CLI
  installation in the direct-distribution channel. Test coexistence/migration
  and record the bundle-identity/cache policy before freezing identifiers.
- [ ] Audit dependencies' network behavior and privacy-sensitive API usage. Add
  accurate `PrivacyInfo.xcprivacy` entries where required, including valid reasons
  for relevant API uses. Do not declare “Data Not Collected” without checking
  download-host logging, diagnostics and third-party behavior.
  [Required-reason APIs](https://developer.apple.com/documentation/technotes/tn3183-adding-required-reason-api-entries-to-your-privacy-manifest) ·
  [Third-party SDK requirements](https://developer.apple.com/support/third-party-SDK-requirements/)

## 4. TestFlight and review preparation

- [ ] Upload the validated candidate and install it through TestFlight on machines
  without the development checkout, Python or Homebrew dependencies.
  [TestFlight](https://developer.apple.com/help/app-store-connect/test-a-beta-version/testflight-overview/)
- [ ] Test the minimum supported macOS version and current macOS release, low-memory
  Apple Silicon hardware, and Intel if included. Reconfirm the minimum after SDK
  and dependency validation rather than silently changing it from macOS 14.
- [ ] Prepare a 1024px icon and genuine screenshots, English and Brazilian
  Portuguese listing copy, category, age rating, copyright and license notices.
- [ ] Publish support and privacy-policy URLs. Describe local transcription
  accurately: initial model downloads require internet; audio is not uploaded
  by the transcription pipeline. Complete privacy, encryption/export-compliance
  and regional business-status questions from the actual app/business facts.
  [Review preparation](https://developer.apple.com/app-store/review/)
- [ ] Provide review steps, a redistributable sample recording, expected output,
  a small-model download path and storage requirements. Explain Metal/CPU choices,
  offline behavior and why the child process exists. Include no login requirement.

Required beta evidence:

| Scenario | Pass condition |
| --- | --- |
| Fresh install | Opens from TestFlight without Terminal or permission workarounds |
| Permissions | Granted/denied/revoked input and output access handled clearly |
| Models | New, interrupted, corrupt and low-space downloads handled; cached model works offline |
| Transcription | Real speech yields usable txt/md/srt/vtt/json; file/folder batch works |
| Acceleration | Metal works on Apple Silicon; CPU fallback tested; GUI stays responsive |
| Shutdown | Cancel and Command-Q during download/load/decode leave no worker or crash report |
| Updates | Beta update preserves models/settings; migration from direct edition is explicit |
| Usability | Keyboard navigation, VoiceOver, readable scaling, dark/light appearance and error recovery checked |

## 5. Submit, release and maintain

- [ ] Submit the tested build with complete metadata; resolve review feedback
  against the same documented requirements. Any changed binary repeats relevant QA.
- [ ] Choose manual release for the first approved version. Verify its public
  product page and a real Store install, download, transcription and export.
- [ ] Add the Store badge/link to the concise README and installation guide after
  the listing is live; explain supported architectures and channel differences.
- [ ] Maintain a release owner, crash/support triage, source/notices availability,
  dependency/SDK refreshes and Store update QA. Set a first-week feedback check.

## First implementation backlog

1. Owner: confirm developer membership, seller identity and rights-review route.
2. Developer: write the macOS payload/license inventory and architecture decision record.
3. Developer: build the sandbox prototype with one input, explicit output folder,
   a tiny model and the isolated inference worker; record signed-build evidence.
4. Developer + owner: enable Developer ID signing/notarization for the next direct release.
5. At the prototype gate, approve the final Store architecture and revise effort estimates.

The roadmap does not change the project license or enroll/pay/upload on the
owner's behalf. Those implementation actions follow their respective milestone
decisions and working, reviewable artifacts.
