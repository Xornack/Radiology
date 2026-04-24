import io
import wave

import numpy as np
import pytest

from src.core.commit_splitter import CommitSplitter, TickResult


class FakeRecorder:
    """Recorder double that exposes a fixed float32 numpy buffer."""

    def __init__(self, samples: np.ndarray, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.channels = 1
        self._samples = samples

    def get_sample_count(self) -> int:
        return len(self._samples)

    def get_wav_bytes_slice(self, start: int, end: int) -> bytes:
        pcm = (self._samples[start:end] * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm.tobytes())
        return buf.getvalue()


class ScriptedSTT:
    """STT double that returns scripted text per transcribe call."""

    def __init__(self, script: list):
        self._script = list(script)
        self.calls: list[bytes] = []

    def transcribe(self, wav_bytes: bytes) -> str:
        self.calls.append(wav_bytes)
        if not self._script:
            return ""
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _tone(duration_s: float, amplitude: float = 0.3, sample_rate: int = 16000):
    t = np.arange(int(sample_rate * duration_s)) / sample_rate
    return (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def _silence(duration_s: float, sample_rate: int = 16000):
    return np.zeros(int(sample_rate * duration_s), dtype=np.float32)


def test_process_tick_with_no_silence_returns_partial_only():
    samples = _tone(1.2)
    splitter = CommitSplitter(FakeRecorder(samples), ScriptedSTT(["partial"]))
    result = splitter.process_tick()
    assert result.commit_text is None
    assert result.partial_text == "partial"


def test_process_tick_returns_none_when_buffer_below_min_partial():
    samples = _tone(0.2)
    splitter = CommitSplitter(FakeRecorder(samples), ScriptedSTT([]))
    result = splitter.process_tick()
    assert result.commit_text is None
    assert result.partial_text is None


def test_process_tick_commits_at_qualifying_silence():
    samples = np.concatenate([_tone(2.5), _silence(0.8), _tone(0.8)])
    stt = ScriptedSTT(["the patient has a cough", "and no fever"])
    splitter = CommitSplitter(FakeRecorder(samples), stt)
    result = splitter.process_tick()
    assert result.commit_text == "the patient has a cough"
    assert result.partial_text == "and no fever"
    committed, commit_idx = splitter.get_committed_snapshot()
    assert committed == ["the patient has a cough"]
    assert abs(commit_idx - 52800) < 800


def test_process_tick_commit_failure_does_not_advance_pointer():
    samples = np.concatenate([_tone(2.5), _silence(0.8), _tone(0.8)])
    stt = ScriptedSTT([RuntimeError("commit transcribe failed"), "still-partial"])
    splitter = CommitSplitter(FakeRecorder(samples), stt)
    result = splitter.process_tick()
    assert result.commit_text is None
    assert result.partial_text == "still-partial"
    committed, commit_idx = splitter.get_committed_snapshot()
    assert committed == []
    assert commit_idx == 0


def test_process_tick_commit_empty_string_does_not_advance_pointer():
    samples = np.concatenate([_tone(2.5), _silence(0.8), _tone(0.8)])
    stt = ScriptedSTT(["", "still-partial"])
    splitter = CommitSplitter(FakeRecorder(samples), stt)
    result = splitter.process_tick()
    assert result.commit_text is None
    assert result.partial_text == "still-partial"
    committed, commit_idx = splitter.get_committed_snapshot()
    assert committed == []
    assert commit_idx == 0


def test_two_consecutive_ticks_with_two_commits():
    # Commit/partial text flows through apply_punctuation(capitalize_first=
    # False), which lowercases a leading capital so mid-session chunks
    # don't inherit stray STT capitals. Scripted values use lowercase to
    # reflect the post-processing contract.
    first_samples = np.concatenate([_tone(2.5), _silence(0.8), _tone(0.8)])
    stt = ScriptedSTT(["a", "b-partial", "b-committed", "c-partial"])

    fake = FakeRecorder(first_samples)
    splitter = CommitSplitter(fake, stt)

    r1 = splitter.process_tick()
    assert r1.commit_text == "a"
    committed_after_1, commit_idx_1 = splitter.get_committed_snapshot()
    assert committed_after_1 == ["a"]

    fake._samples = np.concatenate([
        first_samples, _tone(1.5), _silence(0.8), _tone(0.5),
    ])

    r2 = splitter.process_tick()
    assert r2.commit_text == "b-committed"
    assert r2.partial_text == "c-partial"
    committed_after_2, commit_idx_2 = splitter.get_committed_snapshot()
    assert committed_after_2 == ["a", "b-committed"]
    assert commit_idx_2 > commit_idx_1


def test_reset_clears_state():
    splitter = CommitSplitter(FakeRecorder(_tone(1.0)), ScriptedSTT(["x"]))
    splitter.process_tick()
    splitter.reset()
    committed, commit_idx = splitter.get_committed_snapshot()
    assert committed == []
    assert commit_idx == 0


def test_tickresult_is_a_plain_dataclass():
    r = TickResult(commit_text="a", partial_text="b")
    assert r.commit_text == "a"
    assert r.partial_text == "b"


def test_process_tick_swallows_buffer_boundary_shift():
    """If the recorder buffer shrinks between get_sample_count and the slice
    call (e.g. recorder.start() was called mid-tick), the tick must return
    an empty TickResult instead of propagating ValueError."""

    class ShiftingRecorder:
        def __init__(self, samples: np.ndarray):
            self._samples = samples
            self._raise_next = False

        def get_sample_count(self) -> int:
            return len(self._samples)

        def get_wav_bytes_slice(self, start: int, end: int) -> bytes:
            if self._raise_next:
                raise ValueError(
                    f"end_sample {end} exceeds buffer length 0"
                )
            pcm = (self._samples[start:end] * 32767).astype(np.int16)
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(pcm.tobytes())
            return buf.getvalue()

    rec = ShiftingRecorder(_tone(1.2))
    rec._raise_next = True
    splitter = CommitSplitter(rec, ScriptedSTT([]))
    # Must not raise — must return an empty tick.
    result = splitter.process_tick()
    assert result.commit_text is None
    assert result.partial_text is None
