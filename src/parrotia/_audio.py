"""Self-contained media decoding for the macOS whisper.cpp bundle."""

from __future__ import annotations


def decode_audio(path: str):
    """Decode the first audio stream to contiguous 16 kHz mono float32."""
    import av
    import numpy as np

    chunks = []
    resampler = av.AudioResampler(format="fltp", layout="mono", rate=16000)
    with av.open(path) as container:
        if not container.streams.audio:
            raise ValueError("The selected file has no audio stream.")
        for frame in container.decode(audio=0):
            for output in resampler.resample(frame):
                chunks.append(output.to_ndarray().reshape(-1))
        for output in resampler.resample(None):
            chunks.append(output.to_ndarray().reshape(-1))
    if not chunks:
        return np.empty(0, dtype=np.float32)
    return np.ascontiguousarray(np.concatenate(chunks), dtype=np.float32)
