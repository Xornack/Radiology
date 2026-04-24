"""Tests for the shared STT base class and WAV helpers in src/ai/_common.

These cover the contract that every on-device STT client now inherits:
empty-audio returns "", exception-swallowing in transcribe(), best-effort
warm(), and the WAV format validator. If these break, every concrete client
breaks too.
"""
import io
import wave

import numpy as np
import pytest

from src.ai._common import (
    BaseSTTClient,
    decode_wav_to_float32,
    read_wav_raw_frames,
)


def _wav(samples: np.ndarray, sr: int = 16000, channels: int = 1, width: int = 2) -> bytes:
    pcm = np.clip(samples * 32767, -32768, 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(width)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


class _StubClient(BaseSTTClient):
    """Minimal concrete subclass for exercising the base's contract."""

    name = "Stub"
    supports_streaming = True

    def __init__(self, transcribe_result: str = "hi", load_error: Exception | None = None):
        super().__init__()
        self._transcribe_result = transcribe_result
        self._load_error = load_error
        self.load_count = 0
        self.transcribe_calls = 0

    def _load_impl(self):
        self.load_count += 1
        if self._load_error is not None:
            raise self._load_error
        return object()

    def _transcribe(self, audio_bytes: bytes) -> str:
        self.transcribe_calls += 1
        self._load()
        if isinstance(self._transcribe_result, Exception):
            raise self._transcribe_result
        return self._transcribe_result


def test_empty_audio_short_circuits_before_transcribe():
    client = _StubClient()
    assert client.transcribe(b"") == ""
    # Never reaches inference — so the mock model is never loaded.
    assert client.transcribe_calls == 0
    assert client.load_count == 0


def test_transcribe_returns_empty_on_subclass_exception():
    client = _StubClient(transcribe_result=RuntimeError("boom"))
    assert client.transcribe(b"not-empty") == ""


def test_transcribe_happy_path_returns_subclass_result():
    assert _StubClient(transcribe_result="hello").transcribe(b"audio") == "hello"


def test_warm_swallows_load_errors():
    client = _StubClient(load_error=ImportError("no backend"))
    client.warm()   # must not raise


def test_load_caches_the_model_across_calls():
    """_load is only expected to call _load_impl once per process."""
    client = _StubClient()
    client._load()
    client._load()
    assert client.load_count == 1


def test_cannot_instantiate_base_directly():
    """BaseSTTClient is ABC — missing abstract methods should block instantiation."""
    with pytest.raises(TypeError):
        BaseSTTClient()   # _load_impl and _transcribe are abstract


def test_decode_wav_round_trip():
    samples = np.array([0.0, 0.5, -0.5, 0.1], dtype=np.float32)
    decoded = decode_wav_to_float32(_wav(samples))
    assert decoded.dtype == np.float32
    assert decoded.shape == (4,)
    assert np.allclose(decoded, samples, atol=1e-4)


def test_decode_wav_rejects_wrong_rate():
    assert decode_wav_to_float32(_wav(np.zeros(100, dtype=np.float32), sr=44100)) is None


def test_decode_wav_rejects_stereo():
    # Build a stereo WAV by hand — our recorder never produces this but
    # a misconfigured device might.
    samples = np.zeros(100, dtype=np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(samples.tobytes())
    assert decode_wav_to_float32(buf.getvalue()) is None


def test_decode_wav_empty_frames_returns_zero_length():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"")
    decoded = decode_wav_to_float32(buf.getvalue())
    assert decoded is not None and decoded.size == 0


def test_read_wav_raw_frames_returns_int16_bytes():
    """Vosk wants raw PCM bytes, not float32."""
    samples = np.array([0.0, 0.5, -0.5, 0.1], dtype=np.float32)
    frames = read_wav_raw_frames(_wav(samples))
    assert isinstance(frames, (bytes, bytearray))
    assert len(frames) == 4 * 2   # 4 samples × 2 bytes per int16


def test_read_wav_raw_frames_rejects_wrong_rate():
    assert read_wav_raw_frames(_wav(np.zeros(10, dtype=np.float32), sr=44100)) is None
