"""Verify real codec decoding, resampling and stereo downmixing."""

import wave

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("av")

from parrotia._audio import decode_audio  # noqa: E402


def test_stereo_resampling(tmp_path):
    path = tmp_path / "stereo.wav"
    # A second of non-silent, identical stereo samples at a non-model rate.
    samples = np.full((44100, 2), 8192, dtype=np.int16)
    with wave.open(str(path), "wb") as wav:
        wav.setparams((2, 2, 44100, 0, "NONE", "not compressed"))
        wav.writeframes(samples.tobytes())
    audio = decode_audio(str(path))
    assert audio.shape == (16000,)
    assert audio.dtype == np.float32 and audio.flags.c_contiguous
    assert np.all(audio > 0.2) and np.all(audio < 0.4)
