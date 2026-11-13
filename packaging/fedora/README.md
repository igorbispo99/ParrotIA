# Native Fedora repository candidate

This directory prepares ParrotIA for review in the **official Fedora repositories**
and discovery through GNOME Software. It does not publish a package. The existing
`packaging/linux/build.py` RPM is a separate self-contained installer; it is not the
source package proposed here.

## Current status (2026-11-13)

Target: Fedora 45, x86_64, CPU transcription as the initial supported runtime.
The application RPM is `noarch`; its native dependencies remain architecture specific.
The native spec builds the Python project using Fedora pyproject macros and system
Python dependencies, installs desktop/AppStream metadata and the existing 256px
icon, and runs the full mocked test suite with Xvfb. It does not install binary
PyPI wheels, bundle a Python runtime, disable automatic RPM dependency generation,
or add CUDA extras. This is an unsubmitted candidate, not an approved package.

A real `dnf repoquery` against only Fedora 45 `fedora` and `updates` repositories
found these prerequisites on 2026-11-13:

| Python distribution | Provider / result |
| --- | --- |
| faster-whisper >=1.1.0 | Missing |
| CustomTkinter >=5.2.2,<6 | Missing |
| PyAV >=11,<19 | Missing |
| CTranslate2 >=4,<5 | Missing |
| darkdetect | Missing |
| Pillow >=10 | python3-pillow 12.3.0 |
| ONNX Runtime >=1.14,<2 | python3-onnxruntime 1.26.0 |
| tokenizers >=0.13,<1 | python3-tokenizers 0.23.2 |
| huggingface-hub >=0.21 | python3-huggingface-hub 1.33.0 |
| NumPy | python3-numpy 2.5.4 |
| tqdm | python3-tqdm 4.69.0 |

This is a dated prerequisite inventory, not proof of recursive dependency closure
or runtime compatibility. `audit_dependencies.py` reads direct requirements from
`pyproject.toml`; its transitive baseline follows faster-whisper 1.2.1 and
CustomTkinter 5.2.2 and must be updated when those change. It checks provider
versions too. Native build dependency resolution and Mock remain separate gates.
No binary RPM is offered while prerequisites are absent.

## Build and check

In an expendable Fedora 45 development environment, install the tools listed in
`.github/workflows/fedora.yml`, then run from the project root:

```sh
bash packaging/fedora/prepare.sh
python3 packaging/fedora/audit_dependencies.py --output dist/fedora/dependency-audit.json
```

The audit exits `0` when all inventoried version constraints have providers, `2`
when any is missing or incompatible, and fails on query/network errors. Source
preparation validates the desktop entry and AppStream metadata, builds the sdist
without downloading build dependencies, creates an SRPM and runs rpmlint. Outputs
are under `dist/fedora/`. The SRPM contains source, not an installable application.

The **Fedora preparation** CI workflow uploads the source archive, source RPM,
rpmlint output and dependency evidence. Missing prerequisites produce an explicit
warning and summary; the clean native Mock build is skipped. A green preparation
job does not mean Fedora submission is ready. Once prerequisites become available,
CI attempts the full build in Mock, including generated build/runtime dependencies
and `%check`. Any native build or check failure fails that job.

The build uses `appstreamcli --no-net`, because RPM checks must not need internet.
The screenshot URL targets the upstream `main` branch and will exist after this
change is merged. Before submission, validate it online and confirm the screenshot
matches the supported Fedora UI. The supplied image is a real Linux GUI capture,
not evidence of a completed Fedora runtime test. No file-opening MIME association
is advertised: the current GUI does not accept a file argument.

## Implementation and submission sequence

1. **Package the missing dependencies first.** Check current Fedora dist-git,
   existing review requests and maintainer interest before creating duplicate
   packages. Review/build darkdetect and CustomTkinter (including its font assets),
   CTranslate2 (CPU, Fedora native toolchain/libraries), and PyAV against Fedora's
   `ffmpeg-free` libraries, then faster-whisper against that complete chain. Each
   new package requires its own source/license/dependency review. A COPR build
   can support experiments but does not establish official repository acceptance.
2. **Resolve native compatibility.** Test supported Fedora Python/Tk versions,
   ONNX Runtime and the CPU inference backend. Check the PyAV `<19` constraint
   against the available system FFmpeg API before choosing versions. If an API
   change requires application work, handle it in a separate tested change; do
   not silently loosen constraints or vendor FFmpeg codec wheels.
3. **Complete code, asset and model review.** Verify source provenance and Fedora
   license eligibility for every dependency, font and embedded Silero VAD model.
   Review the selected Whisper model's license, redistribution/source status,
   download behavior and offline cache with Fedora maintainers/legal as needed.
   This candidate neither ships Whisper weights nor downloads them during build
   or tests. The AppStream copy explicitly discloses the initial model download.
   No general approval of arbitrary remotely downloaded models is implied.
4. **Run a clean native build and lifecycle QA.** After the prerequisite packages
   are available in the intended repositories, rebuild the SRPM in Mock. Require
   full `%check`, clean rpmlint review, installation, CLI and GUI launch, decoding
   representative formats supported by Fedora's codec set, real tiny-model CPU
   inference, offline reuse, paths with spaces/Unicode, update and removal. Confirm
   desktop, icon and AppStream IDs match in the installed payload. Check actual
   GNOME Software discovery after Fedora's AppStream catalog generation; local
   XML validation alone does not establish store visibility.
5. **Publish a complete upstream source release.** The current spec's `Source0`
   is the intended GitHub release asset URL. ParrotIA 1.3.1 has no published PyPI
   sdist and no upstream v1.3.1 tag at this check. The local candidate includes
   new packaging not present in an existing upstream archive. Merge/release these
   changes under an appropriate version, synchronize spec/AppStream versions and
   changelog dates, publish its exact sdist, and compare its checksum with the
   review SRPM's source. Do not submit an unavailable Source0 URL or replace an
   existing release archive with different contents.
6. **Open the official review with a maintainer.** Create a Fedora account and
   personally review/accept the Fedora Project Contributor Agreement, follow
   current packager onboarding/sponsorship, and use the current official package
   review process. Attach the public spec, SRPM, source checksums, dependency
   review links and Mock/rpmlint/QA evidence. Resolve review findings before any
   dist-git, Koji, Bodhi and stable repository steps. Do not treat a GitHub PR,
   local RPM, account creation or contributor agreement as package approval.

## Metadata and references

Component/desktop/icon ID: `io.github.igorbispo99.ParrotIA`. The new metainfo XML
is CC0-1.0 (text in `CC0-1.0.txt`, from the SPDX license list); application code
and existing assets retain AGPL-3.0-or-later. The RPM license expression includes
both. Dependency licenses belong to their own RPMs and still need review.

Current Fedora documentation is protected by Anubis in this environment; its
current full text and exact review entry point could not be verified automatically.
The installed Fedora 45 macros (pyproject-rpm-macros 1.24.0) were used to validate
syntax and behavior. Recheck the official documents with the reviewer before
claiming full policy compliance:

- [Fedora packaging guidelines](https://docs.fedoraproject.org/en-US/packaging-guidelines/)
- [Python packaging](https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/)
- [AppData/AppStream packaging](https://docs.fedoraproject.org/en-US/packaging-guidelines/AppData/)
- [New contributor package process](https://docs.fedoraproject.org/en-US/package-maintainers/New_Package_Process_for_New_Contributors/)
- [Fedora legal documentation](https://docs.fedoraproject.org/en-US/legal/)
- [Fedora accounts](https://accounts.fedoraproject.org/)
- [AppStream desktop metadata specification](https://www.freedesktop.org/software/appstream/docs/sect-Metadata-Application.html)
- [Fedora ffmpeg-free package](https://packages.fedoraproject.org/pkgs/ffmpeg/ffmpeg-free/)
