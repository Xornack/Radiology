import numpy as np
import pytest

from src.core.vad import find_commit_point


def _tone(duration_s: float, amplitude: float = 0.3, freq: float = 440.0,
          sample_rate: int = 16000) -> np.ndarray:
    t = np.arange(int(sample_rate * duration_s)) / sample_rate
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _silence(duration_s: float, sample_rate: int = 16000) -> np.ndarray:
    return np.zeros(int(sample_rate * duration_s), dtype=np.float32)


def test_find_commit_point_with_qualifying_silence():
    sr = 16000
    samples = np.concatenate([
        _tone(2.0), _silence(0.8), _tone(1.0),
    ])
    idx = find_commit_point(samples, sample_rate=sr)
    assert idx is not None
    assert abs(idx - 44800) < 800


def test_find_commit_point_no_qualifying_silence_returns_none():
    samples = np.concatenate([_tone(2.0), _silence(0.3), _tone(1.0)])
    assert find_commit_point(samples) is None


def test_find_commit_point_chunk_too_short_returns_none():
    samples = np.concatenate([_tone(1.0), _silence(0.8), _tone(1.0)])
    assert find_commit_point(samples) is None


def test_find_commit_point_all_silence_returns_none():
    samples = _silence(5.0)
    assert find_commit_point(samples) is None


def test_find_commit_point_self_calibrates_across_amplitudes():
    for amp in (0.1, 0.3, 0.9):
        samples = np.concatenate([
            _tone(2.0, amplitude=amp),
            _silence(0.8),
            _tone(1.0, amplitude=amp),
        ])
        idx = find_commit_point(samples)
        assert idx is not None, f"no commit point at amplitude {amp}"


def test_find_commit_point_30s_cap_forces_a_commit():
    sr = 16000
    samples = _tone(35.0, amplitude=0.3)
    idx = find_commit_point(samples, sample_rate=sr)
    assert idx is not None
    last_10s_start = len(samples) - int(10 * sr)
    assert idx > last_10s_start


def test_find_commit_point_returns_none_for_empty_input():
    assert find_commit_point(np.zeros(0, dtype=np.float32)) is None


def test_find_commit_point_respects_custom_min_silence_ms():
    samples = np.concatenate([_tone(2.0), _silence(0.4), _tone(1.0)])
    assert find_commit_point(samples, min_silence_ms=300) is not None
    assert find_commit_point(samples, min_silence_ms=600) is None
