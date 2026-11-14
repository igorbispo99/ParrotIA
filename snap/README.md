# ParrotIA Snap

Status: stable-grade package for amd64 on core24. Strict confinement, CPU inference.
CI builds the snap but never uploads it; store uploads are done manually with `snapcraft upload`.
The snap version follows `parrotia.__version__` (1.4.0 on `main`). The snap bundles
faster-whisper, so it uses the default backend; the whisper.cpp backend is used only
where faster-whisper is missing, such as the Fedora package.

## Build

Use a clean checkout on amd64 Linux with Snapcraft and its LXD build provider:

```sh
sudo snap install snapcraft --classic
snapcraft
sudo snap install --dangerous ./parrotia_*.snap
parrotia --help
parrotia.gui
parrotia.check
```

The `Snap package` GitHub Actions workflow builds the package, installs it under
strict confinement, exercises decoding/Silero/native libraries and the GUI, then
uploads a review artifact. It does not need store credentials or publish anything.
`grade: devel` deliberately prevents promotion to stable before release QA.
The version is read from the literal `__version__` in `src/parrotia/__init__.py`.

`snap/requirements.txt` hashes the complete bootstrap Python dependency set.
The final PyAV 18.1.0, CTranslate2 4.9.0 and NumPy 2.5.4 wheels are rebuilt from
`snap/native-sources.json`, with separately hashed build tools. Their bootstrap
wheel files and private native-library bundles are removed before staging.

FFmpeg 8.1.3 is built as shared libraries with GPL/nonfree components, network
protocols and external-library autodetection disabled. Its release signature was
verified against the official FFmpeg signing key; the signature/key are retained.
CTranslate2 uses the CPU Ruy backend with MKL, OpenMP, CUDA and cuDNN disabled.
NumPy uses its internal BLAS/LAPACK fallback. Performance can differ from PyPI
builds; Whisper matrix multiplication runs through CTranslate2. These choices
are isolated to this Snap and do not change Fedora or Android packaging.

The native source builder retains all original source archives, SHA-256 hashes,
build commands, configure/CMake output and upstream notices under
`$SNAP/share/doc/parrotia/native/`. Builds use at most four compiler jobs. CI
checks actual library versions, configuration/license strings, source hashes and
the absence of the three original wheel-native bundles inside the installed Snap.
Ubuntu package revisions remain recorded by Snapcraft's build manifest.

## Files, privacy and models

Transcription is local. First use of each model contacts Hugging Face and its
storage/CDN services. Audio is not uploaded to a transcription service. The
first download ranges from about 75 MB to 3.1 GB; the default turbo model is
about 1.6 GB. Keep sufficient disk space for model/cache download overhead.

The launcher sets `HF_HOME` to `$SNAP_USER_COMMON/huggingface` and the hub cache to
its `hub` subdirectory. This normally lives under `~/snap/parrotia/common/` and
survives Snap refresh/revert. Hugging Face telemetry is disabled in this package.
The host's existing hidden Hugging Face cache is not reused. After setup, model
loading/transcription can be tested with `HF_HUB_OFFLINE=1`. Removing a snap can
remove its data; export models before uninstalling if you need to preserve them.
Do not rely on automatic snapshots as your only backup.

Non-hidden files owned by you in your home are available via the `home` interface.
For files on mounted external drives, explicitly enable the optional interface:

```sh
sudo snap connect parrotia:removable-media
```

Files outside the allowed paths remain inaccessible. A file picker does not grant
extra permissions. Copy such media into Documents or choose an accessible folder;
select a writable output directory if the source is read-only. The package requests
no microphone, camera, server/network-bind or classic-confinement permission.
The GUI uses X11/XWayland, so native Wayland-only sessions need XWayland available.
NVIDIA runtime wheels are not installed; CPU use is the supported configuration.

## Checks

```sh
parrotia.check                  # WAV decode, VAD, CPU and cache; no model download
parrotia.check --gui            # also constructs/destroys the real GUI
parrotia.check --model tiny     # explicit model download and CPU inference on silence
HF_HUB_OFFLINE=1 parrotia.check --model tiny
```

The installed-package CI generates a spoken fixture and transcribes WAV, MP3,
FLAC, Ogg/Vorbis, M4A/AAC and MP4/AAC through the real CLI, checking all five
export formats and nonempty speech text. It tests Unicode/spaces in paths,
hidden-home denial, optional removable-media access, read-only output failure
and recovery using a writable folder. The real GUI controls and worker threads
exercise transcription, export, damaged-file batch recovery and cancellation
under Xvfb, with a screenshot saved as QA evidence.

CI also installs a second, test-only local revision, verifies offline model-cache
reuse and a common-data marker, then reverts to the original revision and repeats
those checks. That synthetic revision is never preserved as a Store artifact.
The exact original artifact remains the upload candidate. A local sideload test
does not prove Store-signed delivery or every physical desktop configuration;
install and test the first edge revision separately before a stable release.

## Licenses and source

ParrotIA is AGPL-3.0-or-later. The build installs its license and actual application/
Snap build sources under `$SNAP/share/doc/parrotia/`. `python-dependencies.json`
records installed distribution versions/license metadata and copied notice paths.
Wheel-provided license/notice files are preserved under
`$SNAP/share/licenses/parrotia/python/`. Ubuntu packages retain their copyright
files where staged. This generated inventory is evidence, not legal clearance.

The native source archives accompany the binary in the same downloadable Snap.
For example, copy them from `/snap/parrotia/current/share/doc/parrotia/native/`
after installation. FFmpeg is dynamically linked under `$SNAP/usr/lib`; users
can rebuild compatible libraries from the included sources/configuration,
replace those libraries in an unpacked copy, repack with `snap pack`, and install
the modified Snap locally with `sudo snap install --dangerous <modified.snap>`.
No EULA restricts modification, reverse engineering or relinking.

Additional embedded-asset notices and provenance are recorded in
`snap/licenses/SOURCES.md`. The Roboto fonts identify Apache-2.0 in their embedded
metadata; their text and copyright notice are now included. The Silero VAD asset
is hash-matched to faster-whisper 1.2.1 and retains the Silero Team MIT notice.
`snap/assets.json` makes the build fail if any reviewed font/VAD asset changes.
`snap/model-repositories.json` records the current MIT declarations and commit
identities of the seven offered model repositories. Model downloads follow their
upstream repositories at runtime; future upstream changes require renewed review.
The weights are not included in the Snap.

## Owner onboarding and publication

Once installed-package QA and the license/source gates pass:

1. Sign in/register at https://dashboard.snapcraft.io/ as the upstream publisher;
   read and accept the agreements shown there and secure the account.
2. `parrotia` is reserved by the owner (publisher `igorbispo`, confirmed in the dashboard).
3. After the first revision unlocks the listing editor, fill in the listing with the recipe description, icon, Linux screenshots,
   source/support links, first-model download/storage needs and CPU support.
4. Log in with `snapcraft login`, then upload the reviewed artifact to edge:
   `snapcraft upload --release=latest/edge <artifact.snap>`.
5. Resolve review findings and install from edge on a separate machine. After QA,
   change to `grade: stable`, build/retest that candidate, and upload/promote its
   exact reviewed revision through candidate to stable. Do not promote an older
   development-grade artifact or silently rebuild different inputs for promotion.

The publisher must provide support and maintain dependencies/source availability.
There is no automated upload and no credential is stored in the repository.

Official references:
- https://ubuntu.com/docs/snapcraft/9/how-to/publishing/publish-a-snap/
- https://canonical.com/legal/terms-and-policies/snap-store-terms
- https://snapcraft.io/docs/reference/interfaces/home-interface/
- https://snapcraft.io/docs/reference/interfaces/removable-media-interface/
