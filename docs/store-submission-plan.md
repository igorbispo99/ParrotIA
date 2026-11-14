# Snap Store and official Fedora submission plan

Research date: **12 November 2026**. Checkout inspected: **ParrotIA 1.3.1**.

Scope: Snap Store and **official Fedora repositories, with visibility in GNOME Software**, as selected by the owner. This document covers preparation and implementation planning. Fedora packaging work began on 13 November 2026 (see **Fedora progress** below). Account changes, external submissions and publication have not begun.

## Fedora progress (13 November 2026)

### Work package 0 result: dependency survey

Official repository metadata was queried in clean `fedora:43`, `44`, `45` and `rawhide` (46) containers on x86_64 with `dnf repoquery --whatprovides 'python3dist(...)'`, plus name searches. Bugzilla's Package Review component was searched for existing requests.

| Dependency | F43 | F44 | F45 | Rawhide | Review request |
| --- | --- | --- | --- | --- | --- |
| faster-whisper | missing | missing | missing | missing | none found |
| ctranslate2 (C++ and Python) | missing | missing | missing | missing | none found |
| av (PyAV) | missing | missing | missing | missing | none found |
| customtkinter | missing | missing | missing | missing | none found |
| darkdetect | missing | missing | missing | missing | none found |
| onnxruntime, huggingface-hub, tokenizers, tqdm, numpy, pillow, packaging | present | present | present | present | n/a |
| whisper-cpp | | 1.8.1 | 1.8.3 | 1.9.3 | n/a |
| python3-pywhispercpp (MIT, x86_64 only) | | 1.4.0 | 1.5.0 | 1.5.0 | #2420917, accepted Dec 2025 |
| ffmpeg-free | 7.1 | 8.1 | 9.0 | 9.0 | n/a |
| System Python | 3.14 | 3.14 | 3.15 | 3.15 | n/a |

`python3-whisper` in Fedora is Graphite's time-series database, unrelated to speech recognition.

**Decision (owner, 13 November 2026):** the Fedora package uses a new **whisper.cpp backend** built on Fedora's `python3-pywhispercpp`, rather than submitting five new packages for the faster-whisper stack. Only two small pure-Python packages remain to add: `python-darkdetect` and `python-customtkinter`. faster-whisper remains the default everywhere it is installed.

### Implemented and verified

- `src/parrotia/_whispercpp.py` adds a whisper.cpp backend. `Transcriber` selects a backend automatically, or from `PARROTIA_BACKEND`/`--backend`. Model downloads are pinned to exact Hugging Face revisions (`ggerganov/whisper.cpp@5359861c`, `ggml-org/whisper-vad@9ffd54a1`; both model cards declare MIT), verified by SHA-256, written atomically and resumable. Audio is decoded through the `ffmpeg` CLI. VAD uses Silero v5.1.2 in GGML form. Older bindings (pywhispercpp 1.4 on F44) are feature-detected: they run without VAD, and cancel takes effect when the current decode finishes.
- Desktop identity `io.github.igorbispo99.ParrotIA` covers the desktop entry, hicolor icon, AppStream MetaInfo and the Tk window class. The window's WM_CLASS instance equals the desktop ID, confirmed with `xprop`.
- `packaging/fedora/{python-darkdetect,python-customtkinter,parrotia}.spec` use the current pyproject macros, `%autorelease`, and `ExclusiveArch: x86_64 noarch` because of pywhispercpp. The faster-whisper and PyAV requirements are removed in `%prep`. The specs explicitly require `/usr/bin/ffmpeg`, `python3-tkinter` and `python3-pillow-tk` (Fedora splits out `PIL.ImageTk`). customtkinter's bundled Roboto is replaced by symlinks to `google-roboto-fonts`.
- `pyproject.toml` uses an SPDX `license` string with `license-files`; Rawhide's setuptools deprecates the TOML-table form after February 2027. F43–F45 ship setuptools 78–83, which is at least the 77 required.
- Evidence gathered in containers:
  - Mock chain builds (darkdetect → customtkinter → parrotia) pass `%check` in clean buildroots. That covers desktop-file-validate, `appstreamcli validate` (one pedantic note about uppercase letters in the ID) and pytest (mocked engines).
  - `dnf install` of the built RPMs on a clean F45 pulls every dependency from the official repositories.
  - As an unprivileged user, the CLI transcribed synthesized speech and the GUI launched from the installed entry point. Removal was clean.
  - Real CLI transcription was also verified on F44, F45 and Rawhide.

### Remaining before review submission

1. **Release:** tag an upstream release containing this work (proposed 1.4.0) and set the spec `Version` to it. `Source` points at `archive/v%{version}`.
2. **Policy recheck (work package 0, step 1):** read current Packaging/Python/Review guidelines through an accessible channel. Confirm Bugzilla versus Forge as the review entry point.
3. **Reviewer questions to raise:**
   - Runtime model downloads. Weights are not packaged; they are pinned and verified, and the user's data directory can be overridden for offline use.
   - customtkinter's `CustomTkinter_shapes_font.otf`.
   - customtkinter copying fonts into `~/.fonts` at runtime, which is upstream behavior.
   - customtkinter's MIT LICENSE contradicting its CC0 `setup.cfg` metadata.
4. **rpmlint items to explain or fix:**
   - `dangling-symlink` on the Roboto links: expected, since the target comes from the required font package.
   - `python-leftover-require` for tkinter and pillow-tk: no `python3dist()` provider exists for either.
   - `no-manual-page-for-binary`: optional; could be generated from argparse.
5. **Owner actions:** Fedora account, FPCA, packager sponsorship. Then submit reviews in dependency order: darkdetect, customtkinter, parrotia.
6. **After acceptance:** Koji builds, Bodhi updates per branch, and GNOME Software discovery testing on a real Fedora Workstation (work package 5).

## Recommendation and readiness

Prepare a strictly confined, CPU-capable Snap first. At the same time, investigate Fedora eligibility before investing in a production Fedora spec. Share desktop metadata, licensing records and model/cache improvements across both routes.

The existing RPM is a standalone installer. Its PyInstaller payload is unsuitable as the basis for the proposed official Fedora source package. Fedora inclusion is a distribution-maintenance process; GNOME Software visibility additionally depends on application metadata reaching Fedora's catalog.

| Destination | Assessment | Main work before submission |
| --- | --- | --- |
| Snap Store | Technically plausible; not built or reviewed | Recipe, Tk runtime, confinement, cache paths, payload licensing, installed-package QA, listing |
| Official Fedora repositories | Feasibility remains conditional | Current policy verification, complete source-buildable dependencies, model/VAD treatment, codec compatibility, native RPM, sponsorship/review |
| GNOME Software through Fedora | Part of the selected Fedora objective | Desktop entry, icons, AppStream metadata, catalog ingestion and desktop verification |

CPU inference is the proposed supported baseline for the first store release. NVIDIA support needs separate runtime, redistribution and confinement work. This is an engineering recommendation, not a platform requirement.

## Evidence and verification limits

Repository inspection covered `pyproject.toml`, `LICENSE`, `MANIFEST.in`, the engine and GUI, packaging, tests and release workflows. Installed Python metadata was inspected as an audit aid; the Windows development environment does not establish a Linux release's payload or compatibility.

Canonical's published terms, Snap documentation, Fedora package listings and AppStream specifications were readable. Several current Fedora Docs and Forge pages returned Anubis access-denied pages. Readable Fedora wiki copies include explicitly old guidance: they provide background, **not a completed verification of current policy**. Current Fedora rules, the review entry point and model eligibility must be rechecked before submission, with a maintainer where needed. Neither platform has confirmed acceptance.

Here, **observed** means found in the checkout; **verified source** means readable primary documentation; **proposed** means an engineering choice; **open** means further evidence or a platform decision is needed.

## Terms and policy implications

### Snap Store

The published [Snap Store Terms of Service](https://canonical.com/legal/terms-and-policies/snap-store-terms), dated October 2020, have these practical consequences:

- Secure the publisher account and maintain accurate details (§3).
- Have authority and rights to distribute the application and third-party material; respect privacy and applicable law (§§4–5).
- Grant Canonical rights to test/distribute the Snap and use supplied branding (§6).
- Include and identify licenses; open-source obligations remain applicable (§6).
- Canonical may remove a Snap; removal does not uninstall existing copies (§4).
- Provide user support yourself (§7).
- Terms can change upon posting (§11). Limited liability, indemnity obligations and English law/courts apply (§§14–15).

The separate [Developer terms](https://canonical.com/legal/developer-terms-and-conditions) require testing before submission, third-party permission, license inclusion and legal/export compliance (§§2–3, 15). Their payment provisions exclude free apps (§4). They and the store-specific terms have different indemnity language; do not assume the general open-source exception eliminates the store-specific obligation. The owner should review the agreements actually presented during onboarding before accepting them.

Proposed implementation: publish as the upstream maintainer, identify `AGPL-3.0-or-later`, include actual payload notices, provide release-specific source/build information, and accurately describe network downloads and offline operation. Account agreement acceptance is a later owner action.

### Official Fedora

The [preserved review guidelines](https://fedoraproject.org/wiki/Packaging/ReviewGuidelines) cover source verification, license matching, dependency declarations, file ownership, architecture handling and desktop integration. They point to the [current Review Guidelines](https://docs.fedoraproject.org/en-US/packaging-guidelines/ReviewGuidelines/), which were inaccessible during this review.

The [preserved packaging guidance](https://fedoraproject.org/wiki/User:Tibbs/SensitiveSpecs) requires source-built program binaries, offline builds, system-library use where supported and documented handling of unavoidable bundles. It warns against essential external code downloads. Confirm current wording in the [Packaging Guidelines](https://docs.fedoraproject.org/en-US/packaging-guidelines/) and [what can be packaged](https://docs.fedoraproject.org/en-US/packaging-guidelines/what-can-be-packaged/) before claiming compliance. Describing Fedora as prohibiting every kind of bundling would oversimplify the policy.

Fedora's [FPCA announcement](https://communityblog.fedoraproject.org/fedoras-default-license-for-content-is-now-cc-by-sa-4-0/) explains that contributors sign the agreement, which does not assign copyright or override explicit upstream licenses. The owner must read the [current FPCA](https://docs.fedoraproject.org/en-US/legal/fpca/) during onboarding. Retain ParrotIA's declared AGPL license, confirm its current Fedora license-data status, and audit other shipped materials separately.

**Open model question:** evaluate Whisper weights and faster-whisper's packaged Silero ONNX VAD separately from executable dependencies. Downloaded weights are not automatically downloaded program code. A model card declaring MIT also does not establish Fedora approval of every artifact or download arrangement. Seek current reviewer/Legal guidance where unclear. The [Fedora AI/ML SIG](https://fedoraproject.org/wiki/SIGs/AI-ML) is a technical coordination point, not a substitute for approval.

**Verified codec constraint:** Fedora's [ffmpeg-free listing](https://packages.fedoraproject.org/pkgs/ffmpeg/ffmpeg-free/) explicitly describes limited codec support. Use permitted system libraries and test actual audio streams. File extensions do not establish codec compatibility. The basic supported workflow must not require a third-party repository.

### Flathub clarification

Flathub is outside the selected scope. Its current [generative AI policy](https://docs.flathub.org/docs/for-app-authors/requirements#generative-ai-policy) prohibits AI-generated/assisted manifests and AI-automated submission/review interactions; other included AI-generated materials require disclosure. If reconsidered, those prohibited activities must be handled by a human. This plan supplies no Flathub manifest or submission text.

## Project gap analysis

| Observed evidence | Implication and planned response |
| --- | --- |
| `packaging/linux/build.py` installs a frozen `/opt/parrotia` bundle; its generated RPM disables automatic dependencies and normal post-processing | Implement independent source-based Fedora packaging using system Python and normal RPM processing |
| `packaging/ParrotIA.spec` is a PyInstaller spec | Introduce a distinct RPM spec at `packaging/fedora/parrotia.spec` |
| Desktop entry hardcodes `/opt/parrotia/parrotia-gui` | Add shared desktop metadata with distribution-appropriate launchers |
| Icons exist; no AppStream MetaInfo exists | Add coordinated application/desktop/icon identity and validated upstream MetaInfo |
| No Snap recipe or Snap workflow | Add `snap/snapcraft.yaml` and dedicated CI |
| Dependencies include `faster-whisper>=1.1.0`, CustomTkinter `<6`, Pillow and `av>=11,<19` | Verify constraints against each Fedora branch's Python and native libraries |
| Optional CUDA extra installs NVIDIA wheels | Keep them outside the proposed Fedora CPU build; investigate Snap GPU support separately |
| `_load_model()` delegates model selection/download to faster-whisper | Establish an auditable repository/revision and offline/local-model strategy |
| Cache check treats any snapshot directory as cached and returns true on errors | Distinguish complete, partial and unknown cache state |
| GUI uses Tk dialogs and writes beside input by default | Test sandbox paths and readable output-location/permission errors |
| GUI displays download size/status after starting; no explicit download decision found in that flow | Provide an informed initial download flow and useful interruption/retry behavior |
| Linux CI tests the frozen installer on Ubuntu and Fedora 43 container | Add native Fedora source-build checks and real desktop/store validation |
| Python test matrix ends at 3.12 | Add system-Python coverage for selected Fedora branches |
| `.gitignore` ignores arbitrary specs, Markdown, text and JSON | Add narrow exceptions for future distribution artifacts |

`MANIFEST.in` currently includes neither Snap YAML nor MetaInfo XML patterns. Reproduction-related packaging files must be present in the release source archive. The top-level AGPL license alone is not a license inventory of the frozen application.

## Work package 0: Fedora feasibility and release contract

Owner: developer; owner handles account decisions; Fedora reviewer resolves policy questions. Dependency: none.

1. Read current packaging, Python, licensing, review and new-contributor policies through an accessible official channel. Record date, authoritative links and exceptions. Confirm whether the supported review entry point remains Bugzilla or has moved to Fedora Forge. Fedora's [Forge review project announcement](https://communityblog.fedoraproject.org/gsoc-2025-bringing-package-reviews-to-forgejo/) establishes work on a replacement, not that it is now mandatory.
2. Select currently supported Fedora branches and architectures. Begin Snap validation on `amd64`. Do not copy Fedora 43 from existing CI or advertise `aarch64` without testing.
3. Query official repository metadata in a clean Fedora environment. Match Python distribution provides rather than guessed RPM names. Run later:

   ```sh
   dnf repoquery --whatprovides 'python3dist(faster-whisper)'
   dnf repoquery --whatprovides 'python3dist(ctranslate2)'
   dnf repoquery --whatprovides 'python3dist(customtkinter)'
   dnf repoquery --whatprovides 'python3dist(av)'
   dnf repoquery --whatprovides 'python3dist(onnxruntime)'
   ```

4. Build a dependency matrix: source, required constraint, Fedora provider/version/branch, build requirements, license, bundled code/fonts/data, maintainer and missing-package work. Include tokenizers, Hugging Face Hub, tqdm, NumPy, darkdetect, Pillow, Tcl/Tk and native inference/media libraries, with transitive dependencies.
5. Use official repository metadata and Dist-Git to establish package status. Missing search-engine results do not prove absence. Readable official listings confirm [ONNX Runtime](https://packages.fedoraproject.org/pkgs/onnxruntime/onnxruntime/) and [Hugging Face Hub](https://packages.fedoraproject.org/pkgs/python-huggingface-hub/python3-huggingface-hub/) exist; compatible Python bindings, versions and dependency closure remain to be verified.
6. Resolve Whisper and Silero treatment with the reviewer. If permitted weights must be packaged, plan separately reviewed model/data packaging and evaluate size, provenance and maintenance.

**Exit criterion:** credible source-build route using acceptable dependencies and an agreed model strategy. Missing dependencies become separate packaging/review tasks and must be built in dependency order. Copr can help development but does not satisfy official inclusion. Keep Fedora readiness conditional until this gate passes.

## Work package 1: Licensing and provenance

Owner: developer; owner resolves rights/authorship questions. Dependency: release scope; Snap inventory can start immediately.

- Inventory the actual Linux payload: native libraries, codec configurations, fonts, icons, VAD data and optional runtimes. Development-environment license metadata is only an audit aid.
- Audit CustomTkinter's Roboto and shapes fonts separately. Check current Fedora font policy and investigate system-font substitution or dependency patches.
- For every model record canonical repository, exact revision, origin, license, redistribution evidence and required tokenizer/config files. The configured default [redirects to Dropbox Dash's converted turbo model](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo), whose card declares MIT. Verify dependency behavior and cache migration before changing identifiers.
- Provide release-specific corresponding source, patches and build instructions, with clear directions beside binary downloads. Preserve third-party notices and applicable source/relinking obligations. A link only to ParrotIA's repository may not cover bundled components. The existing `LICENSE`, especially §§4–6, is the primary project license text.
- Document privacy/network behavior: inference location, model/metadata services, local storage and lifecycle. Verify dependency telemetry before claiming there is none.

Proposed outputs: `docs/distribution-licenses.md`, a third-party notice inventory, a model provenance table, source-access instructions and privacy/network documentation. A separate mandatory privacy-policy webpage was not established by this review.

**Exit criterion:** every shipped component and offered model is accounted for; unresolved rights or incompatible terms stop release of the affected payload.

## Work package 2: Shared desktop and runtime preparation

Owner: developer. Dependencies: identity and asset rights.

Choose a stable reverse-DNS ID associated with upstream, provisionally `io.github.igorbispo99.ParrotIA`. Coordinate desktop basename, icon and MetaInfo launch linkage. Install the desktop file, hicolor icon and MetaInfo through each route.

Use a permissive metadata license such as `CC0-1.0`, keep the project license `AGPL-3.0-or-later`, and include name, summary, description, homepage/support links, screenshots and releases. Validate the installed tree as well as the XML. The [AppStream specification](https://www.freedesktop.org/software/appstream/docs/chap-Metadata.html) defines locations, identifiers, metadata licensing and desktop linkage.

Configure package-aware model/cache paths before lazy Hugging Face imports. For Snap, propose `HF_HOME=$SNAP_USER_COMMON/huggingface` so models survive revision changes. Respect explicit configuration outside Snap. Check full offline loading, disk space, partial downloads, retry and refresh/revert behavior; avoid silent model deletion on upgrades.

Expose local-model/offline configuration where required by the agreed Fedora strategy. Keep the core UI-agnostic. Improve network/download notices and output errors. These are product recommendations, not claimed blanket store mandates.

**Exit criterion:** metadata validates and GUI/CLI workflows pass with temporary homes, incomplete caches, offline use and restricted output directories.

## Work package 3: Snap implementation

Owner: developer. Dependencies: work packages 1–2; Fedora dependency reviews need not hold it up.

Create `snap/snapcraft.yaml`, necessary helpers and `.github/workflows/snap.yml`. Prefer installing the source project through Snapcraft's Python workflow over nesting the frozen installer. Stage audited inference/media dependencies plus Tcl/Tk, fonts and desktop libraries. Canonical documents this in [Craft a Python app](https://ubuntu.com/docs/snapcraft/9/how-to/integrations/craft-a-python-app/).

Choose a supported base; `core24` is a candidate because Python 3.12 matches existing CI. Compare current supported bases before fixing it. Record/pin the tested release dependency set with hashes or equivalent provenance while retaining normal source-consumer constraints. No Whisper download should occur during construction.

Use strict confinement. Development grade is appropriate during development; a stable release candidate needs stable grade. Package separate CLI and GUI commands, potentially `parrotia` and `parrotia.gui`. Do not presume an unqualified `parrotia-gui` alias will be auto-granted.

Proposed interfaces: outbound `network` for models, `home` for media/output and `x11` for the current Tk/XWayland GUI. Add desktop interfaces only when needed. Current functionality does not justify microphone recording or network binding. Test Tk fonts/themes rather than assuming a GTK extension configures Tk.

The [home interface](https://snapcraft.io/docs/reference/interfaces/home-interface/) covers user-owned non-hidden home files; it does not grant arbitrary host/hidden-cache access. [Removable media](https://snapcraft.io/docs/reference/interfaces/removable-media-interface/) covers `/media`, `/run/media` and `/mnt` and normally does not auto-connect. If included, document its manual connection and test disconnected/connected behavior. Start with strict confinement; classic publication needs separate Canonical approval.

Run metadata/library checks and installed-package QA in a Linux VM with functional snapd/confinement, including a Wayland session using XWayland. A Docker-only smoke test cannot establish desktop sandbox behavior.

**Exit criterion:** a reproducible candidate installs and transcribes under strict confinement, supports documented paths/offline cache and includes notices, source directions and validated metadata.

## Work package 4: Native Fedora packaging

Owner: developer and future Fedora maintainer. Dependencies: feasibility gate and shared work packages 1–2.

Create `packaging/fedora/parrotia.spec` and native Fedora CI. Use system Python, versioned upstream source, current Fedora Python packaging macros, generated dependency metadata, `%license` and normal RPM post-processing. Likely macros include `%pyproject_buildrequires`, `%pyproject_wheel`, `%pyproject_install` and file-saving macros; verify current guidance before implementation.

Do not reuse the payload RPM, Ubuntu-built native libraries or pip binary wheels. Resolve dependencies from Fedora; package missing ones separately from source. Install CLI/GUI entry points and standard desktop assets. The application may qualify as `noarch` while native dependencies remain architecture-specific; confirm during review.

Build PyAV against allowed system FFmpeg. Check `av<19` against each branch's Python/FFmpeg/PyAV versions. Resolve incompatibilities through tested upstream fixes or reviewer-approved packaging; deleting a version bound alone does not prove compatibility.

Run clean Mock SRPM/binary builds, pytest with Xvfb, `rpmlint`, desktop/AppStream validation and installed CLI/GUI/lifecycle tests. Builds/checks must work offline after declared inputs are staged. Model-download tests belong in separate, explicitly networked QA, not `%check`.

Plan dependency builds in order, Rawhide first, then supported branches and their applicable Bodhi update process. Preserve normal dependency and build-root processing.

**Exit criterion:** clean source rebuild using declared acceptable inputs/dependencies, working CPU/VAD inference, correct desktop integration and review evidence with explained lint exceptions.

## Work package 5: Accounts, review and publication

Owner: project owner for agreements/accounts; developer or sponsored maintainer for operations. Dependency: concrete tested artifacts.

**Snap:** create/use the upstream publisher account, review the presented agreements and check/register `parrotia` (availability not verified). Prepare description, icon, screenshots, support/source links, download/storage disclosure and CPU/architecture support statement. Authenticate; upload to `latest/edge`; resolve review results; test store installation on another host; promote the same tested revision through beta/candidate to stable as appropriate. Canonical's [publishing guide](https://ubuntu.com/docs/snapcraft/9/how-to/publishing/publish-a-snap/) establishes account/name registration, automated review and separate-host installation testing. Staged promotion is our release recommendation.

**Fedora:** use a Fedora account with the applicable contributor agreement and packager onboarding. Secure sponsorship if needed or work with an existing sponsored maintainer. Reconfirm the [new-contributor process](https://docs.fedoraproject.org/en-US/package-maintainers/New_Package_Process_for_New_Contributors/) and [review process](https://docs.fedoraproject.org/en-US/package-maintainers/Package_Review_Process/). Prepare spec, SRPM, checksums, build logs, dependency reviews, license/model findings and lint results before submitting. Resolve review feedback, request repository/branches via the current process, import sources, build in Koji and follow branch-specific update rules. Exact forms/commands await the current-policy check.

After repository and catalog publication, verify GNOME Software finds ParrotIA with the **Fedora repository** as source, displays the icon/screenshots and can install/launch it. Test transcription and removal. MetaInfo alone does not guarantee immediate visibility.

**Exit criterion:** working Snap stable release and official Fedora package/catalog availability on selected branches. Local build success does not meet this criterion; external queue times are outside project control.

## Work package 6: Ongoing maintenance

Name a publisher and Fedora maintainer, preferably with a backup. Document release ownership, support/bug triage, vulnerability response, base/dependency refreshes, Fedora rebuilds, model provenance updates and feature differences. Add narrowly scoped protected CI publishing credentials only after manual publication works. Preserve source/notices and test update/revert recovery. A previously downloadable revision is not automatically a safe rollback target.

## Acceptance test matrix

| Area | Required evidence |
| --- | --- |
| Integrity | Source/version alignment, recorded inputs, correct architecture, notices/source directions, passing validators |
| CPU | Real short recording transcribes with int8 without NVIDIA libraries; VAD loads |
| Offline | Complete setup works with network disabled; empty/partial caches explain the failure |
| Download | Correct repository/revision, writable cache, clear size/network information, interrupted-download recovery and low-space handling |
| Files | Single/folder batches, unicode/spaces, beside-input/chosen output, read-only destinations, per-file failure resilience |
| Snap permissions | Strict install, home paths, denied hidden/outside paths, optional removable media disconnected/connected, CLI paths |
| Desktop | Menu/icon/fonts/dialogs/progress/cancellation on selected Fedora/Ubuntu desktops and Wayland/XWayland |
| Formats | Existing txt/md/srt/vtt/json regression coverage passes against packaged code |
| Lifecycle | Upgrade, Snap refresh/revert, removal/reinstall and documented cache handling; no privileged runtime writes |
| Fedora catalog | Official-repository install, generated AppStream catalog, actual GNOME Software discovery/launch |

Existing mocked-model tests cannot establish real decoding, model loading, sandbox access or acceptance. Run them during implementation alongside package tests. No test suite was run for this documentation-only change.

## Milestones and effort

1. **Feasibility:** current Fedora policy/dependency matrix, Linux payload/model audit and stable desktop identity.
2. **Shared preparation:** metadata, cache/download behavior and first confined Snap build.
3. **Package readiness:** Snap QA/listing; native Fedora SRPM after feasibility passes. Missing dependencies may dominate Fedora work.
4. **Distribution:** owner onboarding, external reviews, publication and end-user verification.

Rough engineering estimates, not commitments: 2–4 working days for initial feasibility/audit/metadata, 3–7 for Snap implementation and desktop QA, and 2–5 for ParrotIA's Fedora packaging **after** dependency/model eligibility is resolved. Missing native packages, legal questions and external review can extend Fedora work to weeks or longer. Refine estimates after milestone 1.

The planning change adds this document and a narrow `.gitignore` exception so it is trackable. The first implementation milestone should begin with work package 0 and the payload/model inventory. Publication follows tested, reviewable artifacts.
