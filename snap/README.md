# ParrotIA Snap

Status: development package for amd64 on core24. Strict confinement, CPU inference.
No store upload or stable release is configured in CI. Fedora and Android work
are independent of this packaging directory; the shared engine is unchanged.

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

`snap/requirements.txt` pins and hashes the Linux Python dependency set, including transitive
packages. Only the recorded binary wheels are accepted. Refresh it in Python 3.12 on amd64 Linux using pip's resolution report;
review license/runtime changes and rerun installed-package checks. Ubuntu package
revisions are recorded by Snapcraft's build manifest and can change on rebuilds.
These pins are isolated from source installs and other platform ports.

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

Also transcribe a real recording with the CLI and GUI; check language, all export
formats, cancellation, batch errors, unicode paths and read-only outputs. Validate
home access, removable media with/without connection, refresh and revert. Run on
a normal Ubuntu desktop with confinement; WSL/direct execution is not equivalent.

## Licenses and source

ParrotIA is AGPL-3.0-or-later. The build installs its license and actual application/
Snap build sources under `$SNAP/share/doc/parrotia/`. `python-dependencies.json`
records installed distribution versions/license metadata and copied notice paths.
Wheel-provided license/notice files are preserved under
`$SNAP/share/licenses/parrotia/python/`. Ubuntu packages retain their copyright
files where staged. This generated inventory is evidence, not legal clearance.

Before publication, review the exact artifact and close these release gates:

- Review every license, including wheel-native dependencies/codecs, CustomTkinter's
  Roboto/shapes fonts and the packaged Silero ONNX asset. Add any absent notices.
- Record corresponding upstream sources and build configurations for bundled
  components; fulfill applicable source/relinking obligations. ParrotIA's source
  archive alone is not the corresponding source for all native wheel libraries.
- Verify the license/provenance of the seven offered Whisper model repositories;
  model weights are downloaded at runtime, not included in the Snap.
- Review the full Snapcraft build manifest and dependency/security scan results.

## Owner onboarding and publication

Once installed-package QA and the license/source gates pass:

1. Sign in/register at https://dashboard.snapcraft.io/ as the upstream publisher;
   read and accept the agreements shown there and secure the account.
2. Check/reserve `parrotia`; availability has not been established by this recipe.
3. Fill in the listing with the recipe description, icon, Linux screenshots,
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
