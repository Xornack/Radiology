"""Shared pytest fixtures.

Kept lean on purpose — only fixtures that multiple test files have
genuinely duplicated belong here. Single-use helpers stay in their
home test file.
"""
import io
import wave

import numpy as np
import pytest


@pytest.fixture
def wav_helper():
    """Build recorder-format WAV bytes (mono 16-bit 16kHz by default) from a
    float sample array in [-1, 1]. Used by the STT client tests, the base-
    class tests, and the audio-pipeline tests — they all need the same shape.
    """
    def _make_wav(
        samples: np.ndarray,
        sr: int = 16000,
        channels: int = 1,
        sampwidth: int = 2,
    ) -> bytes:
        pcm = np.clip(samples * 32767, -32768, 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sampwidth)
            wf.setframerate(sr)
            wf.writeframes(pcm.tobytes())
        return buf.getvalue()

    return _make_wav
