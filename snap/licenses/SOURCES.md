# Supplemental Python dependency licenses

These versioned upstream texts supplement wheels which omit license files.
They do not constitute a complete audit of bundled native libraries.

- `ctranslate2-LICENSE.txt`: https://raw.githubusercontent.com/OpenNMT/CTranslate2/v4.9.0/LICENSE
  SHA-256: `54aa79d9fe3c09e67a16dcd95b9e88676405a6ec174efda31036983cf7672ecb`
- `flatbuffers-LICENSE.txt`: https://raw.githubusercontent.com/google/flatbuffers/v25.12.19/LICENSE
  SHA-256: `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`
- `tokenizers-LICENSE.txt`: https://raw.githubusercontent.com/huggingface/tokenizers/v0.23.3/LICENSE
  SHA-256: `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4`


## Native source builds (2026-11-14)

The Snap rebuilds FFmpeg 8.1.3, PyAV 18.1.0, CTranslate2 4.9.0 and NumPy 2.5.4
from the hash-pinned archives in `snap/native-sources.json`. The native runtime
part includes those exact archives, commands/configuration and copied upstream
notices in `share/doc/parrotia/native/`. CPU submodules are pinned individually:
cpu_features (Apache-2.0), spdlog (MIT), Ruy (Apache-2.0) and cpuinfo (BSD-2-Clause).
Only this CPU backend is compiled. Main project licenses remain in their sources.
FFmpeg reports LGPL-2.1-or-later for the selected configuration. Its signature
was verified with key FCF986EA15E6E293A5644F10B4322F04D67658D8, as published at
https://ffmpeg.org/download.html. The source archive is included alongside the
binary; shared libraries can be replaced in a locally rebuilt/repacked Snap.

## Embedded assets

- Roboto Regular/Medium, embedded version 2.137 (2017): Copyright 2011 Google Inc.
  All Rights Reserved. Embedded font metadata states Apache License 2.0. Text
  retained as `Roboto-APACHE-2.0.txt`, retrieved from the upstream Roboto project:
  https://github.com/googlefonts/roboto-2/blob/main/LICENSE.
- CustomTkinter_shapes_font.otf: distributed in CustomTkinter 5.2.2 under its
  upstream MIT license; the font has blank copyright/license metadata and no
  separate license declaration. Upstream package source/license:
  https://github.com/TomSchimansky/CustomTkinter/tree/5.2.2.
- silero_vad_v6.onnx SHA-256
  4cbf549b8326f60f80f2536d9eefeb450a9abe83365a098031c89719f1be17d2:
  exact asset from faster-whisper 1.2.1, introduced by
  https://github.com/SYSTRAN/faster-whisper/pull/1373. That upstream change links
  Silero VAD v6.0 and its reconstruction script. Silero Team MIT notice retained
  in `Silero-VAD-MIT.txt`, from
  https://github.com/snakers4/silero-vad/blob/v6.0/LICENSE.

The seven offered Whisper repositories currently declare MIT; exact repository
commit identities and declarations are recorded in `snap/model-repositories.json`.
These are dated provenance observations, not a promise about future upstream
revisions or arbitrary user-supplied models. The actual model weights download
separately at runtime and are not distributed in this Snap.
