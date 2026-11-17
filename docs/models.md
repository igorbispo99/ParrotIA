# Models and acceleration

[Documentation](README.md) · [Project overview](../README.md)

## Choosing a model

| Model              | Speed    | Accuracy | Notes |
|--------------------|----------|----------|-------|
| `tiny` / `base`    | Fastest  | Lower    | Quick drafts, low-resource machines |
| `small` / `medium` | Balanced | Good     | Solid everyday choice |
| `large-v3`         | Slowest  | Best     | Highest accuracy |
| `large-v3-turbo`   | Fast     | Great    | **Recommended default** |
| `distil-large-v3`  | Fast     | Great    | English-focused, compact (faster-whisper only) |
| `large-v3-turbo-q5_0` | Faster | Great    | Quantized turbo, about 575 MB (whisper.cpp only) |

All models are free and run entirely on-device.

## NVIDIA GPU acceleration

For NVIDIA acceleration with faster-whisper, install the CUDA 12 runtime wheels:

```bash
pip install "parrotia[cuda]"
```

On Windows, ParrotIA adds CUDA wheel DLL directories to the search path at
startup. On Linux, the CUDA shared libraries must be discoverable by the system
loader. Set **Device → cuda** in the GUI or pass `--device cuda` on the CLI.
If CUDA is unavailable, ParrotIA falls back to the CPU.

## Inference backends

ParrotIA runs Whisper through one of two engines and picks one automatically (whisper.cpp is preferred on macOS):

| Backend | Used when | Notes |
|---------|-----------|-------|
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CTranslate2) | installed (the default outside macOS) | CPU or NVIDIA GPU; all non-quantized models in the table above |
| [whisper.cpp](https://github.com/ggml-org/whisper.cpp) via [pywhispercpp](https://github.com/absadiki/pywhispercpp) | macOS app / Apple Silicon Python 3.10+, or faster-whisper is unavailable (e.g. native Fedora) | Apple Silicon Metal or CPU; adds `large-v3-turbo-q5_0`, a faster quantized turbo; no `distil-large-v3` |

On macOS, whisper.cpp is preferred when installed. Intel Python installations
and macOS Python 3.9 use faster-whisper by default.

To use whisper.cpp on Linux/Windows, install `pywhispercpp` and make sure
`ffmpeg` is on your `PATH`. macOS uses PyAV for decoding; for a macOS source
build, follow the [static runtime instructions](building.md#build-the-macos-app).
Select whisper.cpp with
`--backend whisper.cpp` or by setting `PARROTIA_BACKEND=whisper.cpp`.

## Model downloads and offline use

whisper.cpp models are downloaded from Hugging Face on first use. Each file is
pinned to an exact repository revision and checked against its SHA-256, and an
interrupted download resumes where it stopped. Models go in
`~/Library/Application Support/parrotia/models` on macOS,
`~/.local/share/parrotia/models` on Linux, and `%LOCALAPPDATA%\parrotia\models`
on Windows.
To use a different folder, such as one copied to an offline machine, set
`PARROTIA_MODELS_DIR`.

`PARROTIA_MODELS_DIR` applies to whisper.cpp models. faster-whisper uses the
Hugging Face cache (normally `~/.cache/huggingface/hub`), which can be relocated
with `HF_HUB_CACHE`. Models for the two engines use different formats and are
not interchangeable. Download the model once with the chosen backend before
using ParrotIA offline.

## Device and precision choices

| Backend / hardware | Device choices | Precision |
| --- | --- | --- |
| faster-whisper | `auto`, `cpu`, `cuda` | `auto`, `int8`, `int8_float16`, `float16`, `float32` |
| whisper.cpp on Apple Silicon | `auto`, `metal`, `cpu` | Fixed by the model file; select `auto` |
| whisper.cpp on other platforms | `auto`, `cpu` | Fixed by the model file; select `auto` |

With whisper.cpp, `auto` selects Metal on Apple Silicon and retries model loading
on CPU if Metal loading fails. Explicit `metal` reports failures instead of
silently switching devices. Choose `large-v3-turbo-q5_0` for quantized inference.

Use [benchmark mode](usage.md#benchmarking-model-speed) to compare models on
your own files.
