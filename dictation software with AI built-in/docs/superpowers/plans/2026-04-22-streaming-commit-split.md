# Streaming Commit/Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the streaming transcriber's "re-transcribe the whole buffer" behavior with a commit-pointer + energy-VAD split so partial latency scales with the length of the unconunitted region, not the total dictation length.

**Architecture:** Three layers. Bottom: `src/core/vad.py` is a pure numpy function (`find_commit_point`). Middle: a new `src/core/commit_splitter.py` holds the commit/partial state (commit pointer, committed-text list) as a plain Python class — no Qt, no threads. Top: `src/core/streaming.py` wraps the splitter in a Qt QObject, keeping the existing QTimer tick schedule and adding a `commit_ready` signal alongside the existing `partial_ready`. The orchestrator's Stop path reads the splitter's snapshot via `streaming.get_committed_snapshot()` and only transcribes the remaining partial region; `MainWindow`'s anchor pair `(_partial_start, _partial_len)` is replaced with `(_committed_end, _partial_end)` and gains an `on_commit` slot that locks committed text in place.

**Tech Stack:** `numpy` (already a dep, for the RMS computation in VAD), `PyQt6` (existing), `pytest` + `pytest-qt` (existing dev deps), `io` / `wave` / `threading` (stdlib). No new runtime deps.

**Reference spec:** `docs/superpowers/specs/2026-04-22-streaming-commit-split-design.md`

**Environment note:** The user's current venv has a pre-existing PyQt6 DLL load failure that blocks pytest from collecting `test_main_window.py`, `test_global_hotkey.py`, and `test_mic_listener.py`. This plan's new Qt-dependent tests (`test_streaming.py`, `test_main_window.py` additions) share that blocker. The non-Qt majority (VAD, commit splitter, recorder, orchestrator, integration smoke, profiling scenarios) runs without that dependency. Plan completion requires either fixing the PyQt6 install or accepting that the Qt-test subset reports collection-level failures until it's fixed.

---

## Task 1: Energy-based VAD — `find_commit_point` (TDD)

**Why:** Pure numpy function, no other dependencies. Landing this first makes the downstream splitter tests trivial to write — they just pass a pre-canned VAD result.

**Files:**
- Create: `src/core/vad.py`
- Create: `tests/unit/test_vad.py`

- [ ] **Step 1.1: Write failing tests**

Create `tests/unit/test_vad.py`:

```python
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
    """Tone 2s, silence 800ms, tone 1s. Silence qualifies (>= 600ms) and the
    pre-silence audio is >= 2s (min_chunk_ms). Commit point should land
    near the END of the silence (sample-accurate to within ~50 ms)."""
    sr = 16000
    samples = np.concatenate([
        _tone(2.0), _silence(0.8), _tone(1.0),
    ])
    idx = find_commit_point(samples, sample_rate=sr)
    assert idx is not None
    # Silence ends at 2.0 + 0.8 = 2.8 s = 44800 samples. Allow +/- 800 samples
    # (50 ms) slack for the RMS-window boundary effects.
    assert abs(idx - 44800) < 800


def test_find_commit_point_no_qualifying_silence_returns_none():
    """Tone 2s, silence 300ms, tone 1s. 300 ms < 600 ms min_silence_ms.
    No qualifying commit point."""
    samples = np.concatenate([_tone(2.0), _silence(0.3), _tone(1.0)])
    assert find_commit_point(samples) is None


def test_find_commit_point_chunk_too_short_returns_none():
    """Tone 1s then silence 800ms then tone 1s. Pre-silence audio is only
    1 s, below the 2 s min_chunk_ms. Not a valid commit point."""
    samples = np.concatenate([_tone(1.0), _silence(0.8), _tone(1.0)])
    assert find_commit_point(samples) is None


def test_find_commit_point_all_silence_returns_none():
    samples = _silence(5.0)
    assert find_commit_point(samples) is None


def test_find_commit_point_self_calibrates_across_amplitudes():
    """Same tone-silence-tone shape at three different amplitudes should
    all yield a commit point — threshold must self-calibrate."""
    for amp in (0.1, 0.3, 0.9):
        samples = np.concatenate([
            _tone(2.0, amplitude=amp),
            _silence(0.8),
            _tone(1.0, amplitude=amp),
        ])
        idx = find_commit_point(samples)
        assert idx is not None, f"no commit point at amplitude {amp}"


def test_find_commit_point_30s_cap_forces_a_commit():
    """No natural silence > 600 ms in a 35 s tone, but the fallback must
    still return a commit point inside the last 10 s of the buffer."""
    sr = 16000
    samples = _tone(35.0, amplitude=0.3)
    idx = find_commit_point(samples, sample_rate=sr)
    assert idx is not None
    last_10s_start = len(samples) - int(10 * sr)
    assert idx > last_10s_start


def test_find_commit_point_returns_none_for_empty_input():
    assert find_commit_point(np.zeros(0, dtype=np.float32)) is None


def test_find_commit_point_respects_custom_min_silence_ms():
    """400 ms silence qualifies when min_silence_ms=300."""
    samples = np.concatenate([_tone(2.0), _silence(0.4), _tone(1.0)])
    assert find_commit_point(samples, min_silence_ms=300) is not None
    assert find_commit_point(samples, min_silence_ms=600) is None
```

- [ ] **Step 1.2: Run the tests — expect ImportError**

Run: `python -m pytest tests/unit/test_vad.py -v`
Expected: `ModuleNotFoundError: No module named 'src.core.vad'`.

- [ ] **Step 1.3: Implement `find_commit_point`**

Create `src/core/vad.py`:

```python
"""Energy-based voice-activity detector.

Finds a "commit point" inside an audio buffer: the sample index after
a long-enough silence gap that starts after a long-enough leading
chunk of audio. Used by the streaming transcriber to decide where
it's safe to lock in transcribed text so future ticks don't have to
re-do that work.

Self-calibrating: the RMS threshold is relative to the buffer's own
rolling maximum RMS, so it adapts to mic gain without per-user config.
"""
from typing import Optional

import numpy as np


def find_commit_point(
    samples: np.ndarray,
    sample_rate: int = 16000,
    min_silence_ms: int = 600,
    min_chunk_ms: int = 2000,
    rms_window_ms: int = 30,
    fallback_cap_s: float = 30.0,
    fallback_search_s: float = 10.0,
) -> Optional[int]:
    """Return sample index at end of a qualifying silence, or None.

    Qualifies when: there are >= min_chunk_ms of audio BEFORE a silence
    of >= min_silence_ms. Threshold for "silence" is self-calibrated as
    max(0.002, 0.15 * rolling_max_rms) over non-overlapping windows of
    `rms_window_ms`.

    Fallback: if the buffer is longer than fallback_cap_s AND no natural
    commit point qualifies, return the index at the quietest 100 ms
    window inside the last `fallback_search_s` of the buffer. This
    bounds partial-region growth on continuous-talk dictations.
    """
    if samples.size == 0:
        return None

    win_len = max(1, int(sample_rate * rms_window_ms / 1000))
    n_windows = samples.size // win_len
    if n_windows == 0:
        return None

    # Per-window RMS (L2-norm of fixed-size chunks).
    trimmed = samples[: n_windows * win_len].reshape(n_windows, win_len)
    rms = np.sqrt(np.mean(trimmed.astype(np.float32) ** 2, axis=1))
    rolling_max = np.max(rms) if rms.size else 0.0
    threshold = max(0.002, 0.15 * float(rolling_max))

    min_silence_windows = max(1, int(min_silence_ms / rms_window_ms))
    min_chunk_windows = max(1, int(min_chunk_ms / rms_window_ms))

    # Walk windows, track current silence run. A qualifying run ends
    # AFTER min_chunk_windows of audio have preceded it.
    silence_start: Optional[int] = None
    for i, r in enumerate(rms):
        is_silent = r < threshold
        if is_silent:
            if silence_start is None:
                silence_start = i
        else:
            if silence_start is not None:
                run_len = i - silence_start
                if run_len >= min_silence_windows and silence_start >= min_chunk_windows:
                    # Commit at END of the silence (= current window i start).
                    return i * win_len
                silence_start = None

    # Trailing silence at end-of-buffer (nothing after it).
    if silence_start is not None:
        run_len = n_windows - silence_start
        if run_len >= min_silence_windows and silence_start >= min_chunk_windows:
            return n_windows * win_len

    # Fallback: long buffer with no natural silence — commit at the
    # quietest window inside the last `fallback_search_s`.
    if samples.size >= int(fallback_cap_s * sample_rate):
        search_start_sample = samples.size - int(fallback_search_s * sample_rate)
        search_start_win = max(0, search_start_sample // win_len)
        if search_start_win < n_windows:
            local_min_idx = search_start_win + int(np.argmin(rms[search_start_win:]))
            return local_min_idx * win_len

    return None
```

- [ ] **Step 1.4: Run the tests — expect PASS**

Run: `python -m pytest tests/unit/test_vad.py -v`
Expected: all 8 tests pass.

- [ ] **Step 1.5: Commit**

```bash
git add src/core/vad.py tests/unit/test_vad.py
git commit -m "Streaming: add energy-based find_commit_point VAD"
```

---

## Task 2: Recorder slice access + sample count (TDD)

**Why:** The streaming splitter needs to encode just `[commit_idx, end]` to WAV, and it needs to read the current buffer length without re-encoding the whole thing. Both additions are one-screenful each.

**Files:**
- Modify: `src/hardware/recorder.py`
- Modify: `tests/unit/test_recorder.py`

- [ ] **Step 2.1: Add failing tests**

Open `tests/unit/test_recorder.py`. Append the following tests (leave existing tests untouched):

```python
import io
import wave

import numpy as np

from src.hardware.recorder import AudioRecorder


def _prime_recorder_buffer(rec: AudioRecorder, seconds: float) -> int:
    """Fill the recorder's buffer directly (bypass the sounddevice stream)
    for hermetic tests. Returns the sample count written."""
    n = int(rec.sample_rate * seconds)
    rec._buffer = list(np.zeros(n, dtype=np.float32))
    return n


def test_get_sample_count_matches_buffer_length():
    rec = AudioRecorder()
    _prime_recorder_buffer(rec, 1.5)
    assert rec.get_sample_count() == int(rec.sample_rate * 1.5)


def test_get_sample_count_zero_on_empty_buffer():
    rec = AudioRecorder()
    assert rec.get_sample_count() == 0


def test_get_wav_bytes_slice_returns_requested_range():
    rec = AudioRecorder()
    _prime_recorder_buffer(rec, 3.0)
    start, end = 16000, 32000  # 1 s to 2 s
    wav = rec.get_wav_bytes_slice(start, end)
    with wave.open(io.BytesIO(wav), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == end - start


def test_get_wav_bytes_slice_zero_length_is_valid_empty_wav():
    rec = AudioRecorder()
    _prime_recorder_buffer(rec, 1.0)
    wav = rec.get_wav_bytes_slice(0, 0)
    with wave.open(io.BytesIO(wav), "rb") as wf:
        assert wf.getnframes() == 0


def test_get_wav_bytes_slice_raises_on_out_of_bounds():
    import pytest
    rec = AudioRecorder()
    _prime_recorder_buffer(rec, 1.0)
    with pytest.raises(ValueError):
        rec.get_wav_bytes_slice(0, 99999)  # beyond buffer
    with pytest.raises(ValueError):
        rec.get_wav_bytes_slice(-1, 100)


def test_get_wav_bytes_slice_raises_on_reversed_range():
    import pytest
    rec = AudioRecorder()
    _prime_recorder_buffer(rec, 1.0)
    with pytest.raises(ValueError):
        rec.get_wav_bytes_slice(500, 100)
```

- [ ] **Step 2.2: Run the new tests — expect failure**

Run: `python -m pytest tests/unit/test_recorder.py -v -k "sample_count or wav_bytes_slice"`
Expected: `AttributeError: 'AudioRecorder' object has no attribute 'get_sample_count'` (or similar).

- [ ] **Step 2.3: Implement the additions on `AudioRecorder`**

Edit `src/hardware/recorder.py`. Locate the `get_wav_bytes` method. Immediately after it, add two new methods (they share the same lock pattern):

```python
    def get_sample_count(self) -> int:
        """Current number of captured samples. Lock-safe cheap read."""
        with self._buffer_lock:
            return len(self._buffer)

    def get_wav_bytes_slice(self, start_sample: int, end_sample: int) -> bytes:
        """Encode buffer[start_sample:end_sample] as 16 kHz mono PCM WAV.

        Raises ValueError for reversed or out-of-bounds ranges — silent
        truncation would hide splitter bugs.
        """
        if start_sample < 0 or end_sample < start_sample:
            raise ValueError(
                f"Invalid slice range: [{start_sample}, {end_sample}]"
            )
        with self._buffer_lock:
            buf_len = len(self._buffer)
            if end_sample > buf_len:
                raise ValueError(
                    f"end_sample {end_sample} exceeds buffer length {buf_len}"
                )
            audio_array = np.array(
                self._buffer[start_sample:end_sample], dtype="float32"
            )

        pcm_float = audio_array * 32767
        clipped = np.clip(pcm_float, -32768, 32767)
        pcm = clipped.astype(np.int16)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm.tobytes())
        return buf.getvalue()
```

- [ ] **Step 2.4: Run the new tests — expect PASS**

Run: `python -m pytest tests/unit/test_recorder.py -v -k "sample_count or wav_bytes_slice"`
Expected: all 6 new tests pass.

- [ ] **Step 2.5: Run the whole recorder test file to confirm no regressions**

Run: `python -m pytest tests/unit/test_recorder.py -v`
Expected: all tests pass (old + 6 new).

- [ ] **Step 2.6: Commit**

```bash
git add src/hardware/recorder.py tests/unit/test_recorder.py
git commit -m "Recorder: add get_sample_count + get_wav_bytes_slice"
```

---

## Task 3: `CommitSplitter` — pure commit/partial logic (TDD)

**Why:** All the commit/split logic extracts cleanly into a plain-Python class. This is a deliberate split from the spec's "state on StreamingTranscriber" phrasing: the spec describes the external behavior (Qt signals + accessor); the implementation puts the state in an owned helper so tests don't need pytest-qt. The Qt wrapper in Task 4 becomes a thin signal emitter.

**Files:**
- Create: `src/core/commit_splitter.py`
- Create: `tests/unit/test_commit_splitter.py`

- [ ] **Step 3.1: Write failing tests**

Create `tests/unit/test_commit_splitter.py`:

```python
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
    samples = _tone(0.2)  # below default 0.5 s min_partial_s
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
    # Commit point should be near the end of the 800 ms silence.
    # Silence ends at 2.5 + 0.8 = 3.3 s = 52800 samples; allow +/- 800 slack.
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
    """First tick commits chunk A and partials chunk B. Second tick grows
    the buffer and commits chunk B, partials chunk C."""
    first_samples = np.concatenate([_tone(2.5), _silence(0.8), _tone(0.8)])
    stt = ScriptedSTT(["A", "B-partial", "B-committed", "C-partial"])

    fake = FakeRecorder(first_samples)
    splitter = CommitSplitter(fake, stt)

    r1 = splitter.process_tick()
    assert r1.commit_text == "A"
    committed_after_1, commit_idx_1 = splitter.get_committed_snapshot()
    assert committed_after_1 == ["A"]

    # Grow buffer: append more silence + tone so VAD finds another commit.
    fake._samples = np.concatenate([
        first_samples, _tone(1.5), _silence(0.8), _tone(0.5),
    ])

    r2 = splitter.process_tick()
    assert r2.commit_text == "B-committed"
    assert r2.partial_text == "C-partial"
    committed_after_2, commit_idx_2 = splitter.get_committed_snapshot()
    assert committed_after_2 == ["A", "B-committed"]
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
```

- [ ] **Step 3.2: Run the tests — expect ImportError**

Run: `python -m pytest tests/unit/test_commit_splitter.py -v`
Expected: `ModuleNotFoundError: No module named 'src.core.commit_splitter'`.

- [ ] **Step 3.3: Implement `CommitSplitter`**

Create `src/core/commit_splitter.py`:

```python
"""Commit-and-partial orchestration for streaming dictation.

Owns the audio buffer's "commit pointer" and the running list of
committed transcriptions. `process_tick()` is pure and synchronous —
no threads, no Qt. The Qt wrapper in `streaming.py` schedules calls on
a QTimer and emits the returned text via signals.
"""
from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger

from src.core.vad import find_commit_point
from src.engine.punctuation import apply_punctuation


@dataclass
class TickResult:
    """What one tick produced: zero or one commit, zero or one partial."""

    commit_text: Optional[str] = None
    partial_text: Optional[str] = None


class CommitSplitter:
    def __init__(
        self,
        recorder: Any,
        stt_client: Any,
        sample_rate: int = 16000,
        min_partial_s: float = 0.5,
    ):
        self.recorder = recorder
        self.stt_client = stt_client
        self.sample_rate = sample_rate
        self.min_partial_s = min_partial_s
        self._commit_sample_idx: int = 0
        self._committed_text: list[str] = []

    def reset(self) -> None:
        """Reset commit state. Call at the start of each dictation session."""
        self._commit_sample_idx = 0
        self._committed_text = []

    def get_committed_snapshot(self) -> tuple[list[str], int]:
        """Return (copy of committed_text, commit_sample_idx) atomically.
        Orchestrator calls this on Stop after `streaming.stop()` has
        blocked new ticks."""
        return list(self._committed_text), self._commit_sample_idx

    def process_tick(self) -> TickResult:
        """Run one streaming tick. Returns what needs to be emitted."""
        end_sample = self.recorder.get_sample_count()
        partial_samples = end_sample - self._commit_sample_idx
        if partial_samples < int(self.sample_rate * self.min_partial_s):
            return TickResult()

        # Pull the partial region as a numpy array for VAD. We read WAV
        # bytes from the recorder for the transcribe step; for VAD we
        # want the float samples directly. `recorder._buffer` is a list
        # — accessing it isn't strictly the public API, but we only need
        # a read (the lock guards concurrent writes, not reads of a
        # non-shrinking list). Go through get_wav_bytes_slice + decode
        # to stay within the public API.
        partial_wav = self.recorder.get_wav_bytes_slice(
            self._commit_sample_idx, end_sample
        )
        partial_samples_arr = _decode_wav_to_float32(partial_wav)

        commit_local_idx = find_commit_point(
            partial_samples_arr, sample_rate=self.sample_rate
        )

        commit_text: Optional[str] = None
        if commit_local_idx is not None and commit_local_idx > 0:
            commit_end_global = self._commit_sample_idx + commit_local_idx
            commit_wav = self.recorder.get_wav_bytes_slice(
                self._commit_sample_idx, commit_end_global
            )
            try:
                raw = self.stt_client.transcribe(commit_wav)
            except Exception as e:
                logger.error(f"Commit transcribe failed, skipping commit: {e}")
                raw = ""
            if raw:
                commit_text = apply_punctuation(raw)
                self._committed_text.append(commit_text)
                self._commit_sample_idx = commit_end_global
            # else: don't advance the pointer; next tick retries.

        # Build the post-commit partial region and transcribe it.
        partial_end = end_sample
        partial_start = self._commit_sample_idx
        if partial_end - partial_start <= 0:
            return TickResult(commit_text=commit_text, partial_text=None)

        remainder_wav = self.recorder.get_wav_bytes_slice(
            partial_start, partial_end
        )
        try:
            raw = self.stt_client.transcribe(remainder_wav)
        except Exception as e:
            logger.error(f"Partial transcribe failed: {e}")
            raw = ""
        partial_text = apply_punctuation(raw) if raw else None

        return TickResult(commit_text=commit_text, partial_text=partial_text)


def _decode_wav_to_float32(wav_bytes: bytes):
    """Pull mono int16 PCM out of a 16 kHz mono WAV → float32 numpy."""
    import io
    import wave

    import numpy as np

    with wave.open(io.BytesIO(wav_bytes)) as wf:
        frames = wf.readframes(wf.getnframes())
    if not frames:
        return np.zeros(0, dtype=np.float32)
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
```

- [ ] **Step 3.4: Run the tests — expect PASS**

Run: `python -m pytest tests/unit/test_commit_splitter.py -v`
Expected: all 8 tests pass.

- [ ] **Step 3.5: Commit**

```bash
git add src/core/commit_splitter.py tests/unit/test_commit_splitter.py
git commit -m "Streaming: add CommitSplitter (pure commit/partial logic)"
```

---

## Task 4: `StreamingTranscriber` rework — wire `CommitSplitter` + `commit_ready` signal

**Why:** Replace the current "re-transcribe the buffer" body with a thin wrapper around `CommitSplitter`. Keeps the Qt layer (QTimer tick schedule, thread-hopping signal emissions) while pushing all the logic into the testable splitter.

**Files:**
- Modify: `src/core/streaming.py`
- Create: `tests/unit/test_streaming.py` *(these tests inherit the pre-existing PyQt6 DLL collection issue noted at the top of this plan.)*

- [ ] **Step 4.1: Add failing tests**

Create `tests/unit/test_streaming.py`:

```python
import time

import pytest
from pytestqt.qtbot import QtBot

from src.core.commit_splitter import TickResult
from src.core.streaming import StreamingTranscriber


class DummyRecorder:
    def get_sample_count(self) -> int:
        return 0

    def get_wav_bytes_slice(self, start: int, end: int) -> bytes:
        return b""


class DummySTT:
    def transcribe(self, wav_bytes: bytes) -> str:
        return ""


def test_streaming_transcriber_has_commit_ready_signal(qtbot: QtBot):
    st = StreamingTranscriber(DummyRecorder(), DummySTT())
    assert hasattr(st, "commit_ready")
    assert hasattr(st, "partial_ready")


def test_streaming_transcriber_get_committed_snapshot_delegates(qtbot: QtBot):
    st = StreamingTranscriber(DummyRecorder(), DummySTT())
    committed, idx = st.get_committed_snapshot()
    assert committed == []
    assert idx == 0


def test_streaming_transcriber_emits_commit_and_partial(qtbot: QtBot):
    """Inject a splitter that returns both a commit and a partial from
    process_tick; drive one tick and assert both signals fire."""
    st = StreamingTranscriber(DummyRecorder(), DummySTT())

    # Replace the splitter with a deterministic stub.
    class StubSplitter:
        def __init__(self):
            self.ticks = 0

        def process_tick(self):
            self.ticks += 1
            return TickResult(commit_text="committed", partial_text="partial")

        def reset(self):
            pass

        def get_committed_snapshot(self):
            return ["committed"], 16000

    st._splitter = StubSplitter()
    st.start()

    with qtbot.waitSignal(st.commit_ready, timeout=3000) as commit_sig:
        with qtbot.waitSignal(st.partial_ready, timeout=3000) as partial_sig:
            # Explicitly trigger one tick via the internal entry point.
            st._tick()
            # Wait for the worker thread to finish.
            deadline = time.time() + 2.0
            while st._in_flight and time.time() < deadline:
                time.sleep(0.01)

    assert commit_sig.args == ["committed"]
    assert partial_sig.args == ["partial"]
    st.stop()


def test_streaming_transcriber_skips_signals_after_stop(qtbot: QtBot):
    """If stop() is called before the worker thread finishes, neither
    signal should fire."""
    st = StreamingTranscriber(DummyRecorder(), DummySTT())

    class SlowSplitter:
        def process_tick(self):
            time.sleep(0.2)
            return TickResult(commit_text="c", partial_text="p")

        def reset(self):
            pass

        def get_committed_snapshot(self):
            return [], 0

    st._splitter = SlowSplitter()
    st.start()

    commit_fired = []
    partial_fired = []
    st.commit_ready.connect(lambda t: commit_fired.append(t))
    st.partial_ready.connect(lambda t: partial_fired.append(t))

    st._tick()       # kicks the worker
    st.stop()        # should set _active=False before worker returns

    # Give the worker time to finish — signals must NOT fire.
    time.sleep(0.4)
    assert commit_fired == []
    assert partial_fired == []
```

- [ ] **Step 4.2: Run the tests — expect failure**

Run: `python -m pytest tests/unit/test_streaming.py -v`
Expected: either a PyQt6 DLL collection error (pre-existing env issue — if so, the user needs to resolve that separately) OR tests fail because `commit_ready` signal / `_splitter` attr don't yet exist. Implementation in Step 4.3 makes them pass when the env is working.

- [ ] **Step 4.3: Rewrite `streaming.py`**

Open `src/core/streaming.py`. Replace the entire file with:

```python
import threading
from typing import Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from loguru import logger

from src.core.commit_splitter import CommitSplitter


class StreamingTranscriber(QObject):
    """Qt wrapper around CommitSplitter.

    Schedules ticks on a QTimer and dispatches each tick to a worker
    thread so Qt's event loop stays responsive. Emits `commit_ready`
    once per commit point and `partial_ready` per live-partial update.
    Both signals are queued to the GUI thread automatically by Qt's
    AutoConnection default.
    """
    partial_ready = pyqtSignal(str)
    commit_ready = pyqtSignal(str)

    def __init__(
        self,
        recorder,
        stt_client,
        interval_ms: int = 1500,
        sample_rate: int = 16000,
        parent=None,
    ):
        super().__init__(parent)
        self.recorder = recorder
        self.stt_client = stt_client
        self.interval_ms = interval_ms
        self.sample_rate = sample_rate
        self._splitter = CommitSplitter(
            recorder=recorder,
            stt_client=stt_client,
            sample_rate=sample_rate,
        )
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._worker: Optional[threading.Thread] = None
        self._in_flight = False
        self._active = False

    def start(self):
        self._splitter.reset()
        self._active = True
        self._in_flight = False
        self._timer.start(self.interval_ms)

    def stop(self):
        self._active = False
        self._timer.stop()

    def get_committed_snapshot(self) -> tuple[list[str], int]:
        """Orchestrator uses this on Stop. Safe to call after `stop()`."""
        return self._splitter.get_committed_snapshot()

    # Forward STT client changes to the splitter when the UI swaps
    # backends. main.py writes to streaming.stt_client; keep the
    # splitter in sync.
    @property
    def stt_client(self):
        return self._stt_client

    @stt_client.setter
    def stt_client(self, value):
        self._stt_client = value
        if hasattr(self, "_splitter"):
            self._splitter.stt_client = value

    def _tick(self):
        if self._in_flight or not self._active:
            return
        self._in_flight = True
        self._worker = threading.Thread(target=self._run_tick, daemon=True)
        self._worker.start()

    def _run_tick(self):
        try:
            result = self._splitter.process_tick()
            if not self._active:
                return
            if result.commit_text:
                self.commit_ready.emit(result.commit_text)
            if result.partial_text:
                self.partial_ready.emit(result.partial_text)
        except Exception as e:
            logger.error(f"Streaming tick failed: {e}")
        finally:
            self._in_flight = False
```

- [ ] **Step 4.4: Run the tests**

Run: `python -m pytest tests/unit/test_streaming.py -v`
Expected: all tests pass on a working PyQt6 env. If the pre-existing DLL issue blocks collection, document in the task notes and proceed — the downstream orchestrator/integration tests cover the commit path without Qt.

- [ ] **Step 4.5: Quick sanity-check the profiling harness still works**

The existing `scenario_streaming_tick` imports `src/core/streaming.py` indirectly through `apply_punctuation` only now (the earlier Task-6 refactor made the scenario Qt-free). Verify:

Run: `python -m pytest tests/unit/test_profiling_scenarios.py::test_streaming_tick_runs_three_buffer_sizes -v`
Expected: test passes (scenario doesn't touch StreamingTranscriber directly).

- [ ] **Step 4.6: Commit**

```bash
git add src/core/streaming.py tests/unit/test_streaming.py
git commit -m "Streaming: rework StreamingTranscriber to wrap CommitSplitter + add commit_ready signal"
```

---

## Task 5: Orchestrator Stop-path — read `streaming.get_committed_snapshot()`

**Why:** Without this change, the orchestrator still re-transcribes the whole buffer on Stop even though we've been committing chunks along the way. This task makes Stop read the snapshot and only transcribe the remaining partial region.

**Files:**
- Modify: `src/core/orchestrator.py`
- Modify: `tests/unit/test_orchestrator.py`

- [ ] **Step 5.1: Add failing tests**

Open `tests/unit/test_orchestrator.py`. Add the following tests at the end of the file (leave existing tests untouched):

```python
from unittest.mock import MagicMock

import pytest

from src.core.orchestrator import DictationOrchestrator


class FakeStreamingHandle:
    """Stand-in for StreamingTranscriber's snapshot accessor only."""

    def __init__(self, committed_text: list[str], commit_sample_idx: int):
        self._committed_text = committed_text
        self._commit_sample_idx = commit_sample_idx

    def get_committed_snapshot(self):
        return list(self._committed_text), self._commit_sample_idx


def _mk_orch_with_streaming(
    committed: list[str],
    commit_idx: int,
    remaining_transcription: str = "and no fever",
    buffer_end_sample: int = 100000,
):
    recorder = MagicMock()
    recorder.get_sample_count.return_value = buffer_end_sample
    recorder.get_wav_bytes_slice.return_value = b"remaining-wav-bytes"
    recorder.get_wav_bytes.return_value = b"whole-buffer-wav-bytes"
    stt = MagicMock()
    stt.transcribe.return_value = remaining_transcription
    wedge = MagicMock()
    streaming = FakeStreamingHandle(committed, commit_idx)
    orch = DictationOrchestrator(
        recorder=recorder,
        stt_client=stt,
        wedge=wedge,
        streaming=streaming,
    )
    orch.radiology_mode = False   # keep lexicon out of the assertion
    return orch, recorder, stt, wedge


def test_stop_with_commits_slices_and_concatenates():
    orch, recorder, stt, _ = _mk_orch_with_streaming(
        committed=["The patient has a cough"],
        commit_idx=47000,
        remaining_transcription="and no fever",
    )
    result = orch.handle_trigger_up(mode="inapp")
    recorder.get_wav_bytes_slice.assert_called_once_with(47000, 100000)
    stt.transcribe.assert_called_once_with(b"remaining-wav-bytes")
    # Final text is committed + " " + partial, post-processed.
    assert "cough" in result
    assert "no fever" in result


def test_stop_without_commits_falls_through_to_whole_buffer():
    orch, recorder, stt, _ = _mk_orch_with_streaming(
        committed=[],
        commit_idx=0,
        remaining_transcription="The whole thing",
    )
    result = orch.handle_trigger_up(mode="inapp")
    recorder.get_wav_bytes.assert_called_once()
    recorder.get_wav_bytes_slice.assert_not_called()
    assert "whole thing" in result


def test_stop_wedge_mode_ignores_streaming_handle():
    """Wedge mode still uses the whole-buffer transcribe path."""
    orch, recorder, stt, wedge = _mk_orch_with_streaming(
        committed=["prior chunk"],
        commit_idx=50000,
        remaining_transcription="wedge transcription",
    )
    orch.handle_trigger_up(mode="wedge")
    recorder.get_wav_bytes.assert_called_once()
    # Wedge mode should NOT hit the slice path.
    recorder.get_wav_bytes_slice.assert_not_called()
    wedge.type_text.assert_called_once()


def test_orchestrator_without_streaming_handle_works_as_today():
    """Missing streaming kwarg: behave as pre-change — whole buffer."""
    recorder = MagicMock()
    recorder.get_wav_bytes.return_value = b"whole"
    stt = MagicMock()
    stt.transcribe.return_value = "hello"
    wedge = MagicMock()
    orch = DictationOrchestrator(
        recorder=recorder, stt_client=stt, wedge=wedge,
    )
    orch.radiology_mode = False
    orch.handle_trigger_up(mode="inapp")
    recorder.get_wav_bytes.assert_called_once()
```

- [ ] **Step 5.2: Run the tests — expect failure**

Run: `python -m pytest tests/unit/test_orchestrator.py -v -k "stop_with_commits or stop_without_commits or stop_wedge or without_streaming_handle"`
Expected: tests fail with `TypeError` (no `streaming` kwarg) or the slicing assertion doesn't match.

- [ ] **Step 5.3: Modify `orchestrator.py`**

Open `src/core/orchestrator.py`. Locate the `__init__` method and change its signature + body to accept the optional `streaming` kwarg:

```python
    def __init__(
        self,
        recorder,
        stt_client,
        wedge,
        profiler=None,
        llm_client=None,
        streaming=None,
    ):
        self.recorder = recorder
        self.stt_client = stt_client
        self.wedge = wedge
        self.profiler = profiler
        self.llm_client = llm_client
        self.streaming = streaming
        self._wedge_has_typed = False
        self._wedge_last_terminator = True
        self.radiology_mode = True
```

Then locate `handle_trigger_up`. Replace the body's "Get WAV bytes + Transcribe" section with the commit-aware variant. The method ends up looking like:

```python
    def handle_trigger_up(self, mode: str = "inapp") -> str:
        """
        Process the recording and return the finalized text.

        `mode` selects the output sink:
          - "inapp":  text lands in the caller's UI editor (no external keystrokes).
                      When a `streaming` handle is wired in and has committed
                      chunks, only the remaining partial region is transcribed
                      at Stop; otherwise the full buffer is transcribed as
                      before.
          - "wedge":  text is also typed into the externally focused window via
                      the wedge. Always uses the whole-buffer transcribe.
        """
        logger.info("Dictation stopped. Processing...")
        self.recorder.stop()
        if self.profiler:
            self.profiler.stop("audio_capture")
            self.profiler.start("whisper_stt")

        # 1. Transcribe (commit-aware for in-app mode).
        committed_text: list[str] = []
        commit_idx = 0
        if mode == "inapp" and self.streaming is not None:
            committed_text, commit_idx = self.streaming.get_committed_snapshot()

        if committed_text and commit_idx > 0:
            end_sample = self.recorder.get_sample_count()
            remainder_wav = self.recorder.get_wav_bytes_slice(commit_idx, end_sample)
            remainder_raw = self.stt_client.transcribe(remainder_wav)
            raw_text = " ".join(committed_text + ([remainder_raw] if remainder_raw else []))
        else:
            audio_bytes = self.recorder.get_wav_bytes()
            raw_text = self.stt_client.transcribe(audio_bytes)

        logger.debug(f"Whisper raw: {raw_text!r}")
        if self.profiler:
            self.profiler.stop("whisper_stt")
            self.profiler.start("scrubbing")

        # 2. Scrub PHI on the full concatenated text.
        clean_text = scrub_text(raw_text)

        # 3. Map spoken punctuation tokens.
        cap_first = self._wedge_last_terminator if mode == "wedge" else False
        clean_text = apply_punctuation(clean_text, capitalize_first=cap_first)

        # 4. Optional radiology-vocabulary correction.
        if self.radiology_mode:
            clean_text = correct_radiology(clean_text)
        logger.debug(f"Final text to send: {clean_text!r}")

        if self.profiler:
            self.profiler.stop("scrubbing")
            self.profiler.start("keyboard_wedge")

        # 5. Inject into external application only when explicitly requested.
        if mode == "wedge" and clean_text:
            target = _foreground_window_title()
            to_type = (" " + clean_text) if self._wedge_has_typed else clean_text
            logger.info(
                f"Wedge mode: posting {len(to_type)} chars to focused window. "
                f"Foreground window: {target!r}"
            )
            try:
                self.wedge.type_text(to_type)
                self._wedge_has_typed = True
                self._wedge_last_terminator = clean_text.rstrip()[-1] in ".?!"
            except Exception as e:
                logger.error(f"Keyboard wedge failed: {e}")

        if self.profiler:
            self.profiler.stop("keyboard_wedge")
            total = self.profiler.stop("full_pipeline")
            logger.info(f"Pipeline complete. Total latency: {total:.4f}s")

        return clean_text
```

- [ ] **Step 5.4: Run the orchestrator tests**

Run: `python -m pytest tests/unit/test_orchestrator.py -v`
Expected: all tests pass (old + 4 new).

- [ ] **Step 5.5: Commit**

```bash
git add src/core/orchestrator.py tests/unit/test_orchestrator.py
git commit -m "Orchestrator: commit-aware Stop path (slice + concatenate)"
```

---

## Task 6: `MainWindow` anchors + `on_commit` slot

**Why:** Replace the `_partial_start` / `_partial_len` anchor pair with `_committed_end` / `_partial_end` and add the `on_commit` slot. This is the UI counterpart of the streaming signals. Existing editable-transcript tests must still pass.

**Files:**
- Modify: `src/ui/main_window.py`
- Modify: `tests/unit/test_main_window.py` *(inherits the pre-existing PyQt6 DLL collection issue.)*

- [ ] **Step 6.1: Read the relevant MainWindow methods before editing**

Run: `python -c "from pathlib import Path; p = Path('src/ui/main_window.py'); print(p.read_text()[:100])"` (just to confirm the file path).

Then open `src/ui/main_window.py` with your editor. Locate these three methods to anchor the diffs against:
- `begin_streaming(self)` — currently sets `_partial_start` and `_partial_len`.
- `update_partial(self, text)` — currently uses those two attrs.
- `commit_partial(self, final_text)` — currently uses those two attrs.

- [ ] **Step 6.2: Add failing tests**

Open `tests/unit/test_main_window.py`. Append the following block of tests after the existing partial-related tests (don't remove the existing ones — they'll be updated by the implementation behavior):

```python
def test_on_commit_locks_in_partial_region(qtbot):
    from src.ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    window.begin_streaming()
    window.update_partial("first chunk")
    window.on_commit("first chunk")
    # After commit, the previously-committed region is protected.
    window.update_partial("second")
    text = window.editor.toPlainText()
    assert text == "first chunksecond"


def test_on_commit_with_differing_text_replaces_and_locks(qtbot):
    """Commit text can differ from the previously-displayed partial (STT
    revises with more context). The commit replaces and locks."""
    from src.ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    window.begin_streaming()
    window.update_partial("the patient has a")
    # Commit transcribes a longer slice and returns richer text.
    window.on_commit("the patient has a cough")
    window.update_partial("and")
    text = window.editor.toPlainText()
    assert text == "the patient has a coughand"


def test_on_commit_with_empty_partial_region_is_noop(qtbot):
    from src.ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    window.begin_streaming()
    window.on_commit("shouldnt-appear")
    # No prior update_partial happened; the commit's text IS the new
    # content (previously-empty partial region is replaced).
    text = window.editor.toPlainText()
    assert text == "shouldnt-appear"


def test_commit_partial_after_on_commit_replaces_only_trailing(qtbot):
    from src.ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    window.begin_streaming()
    window.update_partial("locked")
    window.on_commit("locked")
    window.update_partial("tail-partial")
    window.commit_partial("final")
    text = window.editor.toPlainText()
    assert text == "lockedfinal"


def test_commit_partial_empty_clears_trailing_only(qtbot):
    from src.ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    window.begin_streaming()
    window.update_partial("locked")
    window.on_commit("locked")
    window.update_partial("to-be-removed")
    window.commit_partial("")
    text = window.editor.toPlainText()
    assert text == "locked"
```

Find any existing test that references `_partial_start` or `_partial_len` directly (not through the public methods). Replace those with references to `_committed_end` / `_partial_end` — they're the new names for the same concept. If no test references the private attrs, nothing to change here.

- [ ] **Step 6.3: Run the new tests — expect failure**

Run: `python -m pytest tests/unit/test_main_window.py -v -k "on_commit or commit_partial_after"`
Expected: tests fail (either DLL collection issue, or `AttributeError: 'MainWindow' object has no attribute 'on_commit'`).

- [ ] **Step 6.4: Modify `main_window.py`**

In `src/ui/main_window.py`, find the `begin_streaming` / `update_partial` / `commit_partial` trio. Replace them and add `on_commit`:

```python
    def begin_streaming(self):
        """Anchor dictation at the current cursor; reset commit state."""
        cursor = self.editor.textCursor()
        # In-app mode replaces any active selection with the new dictation.
        if cursor.hasSelection():
            cursor.removeSelectedText()
            self.editor.setTextCursor(cursor)
        pos = cursor.position()
        self._committed_end: int = pos
        self._partial_end: int = pos

    def update_partial(self, text: str):
        """Replace [_committed_end, _partial_end] with `text`."""
        if not hasattr(self, "_committed_end") or self._committed_end < 0:
            return
        cursor = self.editor.textCursor()
        cursor.setPosition(self._committed_end)
        cursor.setPosition(self._partial_end, cursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text, self.dictation_format)
        self._partial_end = self._committed_end + len(text)
        # Keep the editing cursor at the tail so user-typed text follows.
        self.editor.setTextCursor(cursor)

    def on_commit(self, text: str):
        """Lock the current partial region as committed.

        Replaces [_committed_end, _partial_end] with `text` (commit
        transcriptions can differ from the displayed partial since more
        audio context is available), then advances _committed_end so
        future update_partial calls don't overwrite the locked text.
        """
        if not hasattr(self, "_committed_end") or self._committed_end < 0:
            return
        cursor = self.editor.textCursor()
        cursor.setPosition(self._committed_end)
        cursor.setPosition(self._partial_end, cursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text, self.dictation_format)
        new_end = self._committed_end + len(text)
        self._committed_end = new_end
        self._partial_end = new_end
        self.editor.setTextCursor(cursor)

    def commit_partial(self, final_text: str):
        """Replace [_committed_end, _partial_end] with final_text (Stop path)."""
        if not hasattr(self, "_committed_end") or self._committed_end < 0:
            return
        cursor = self.editor.textCursor()
        cursor.setPosition(self._committed_end)
        cursor.setPosition(self._partial_end, cursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        if final_text:
            cursor.insertText(final_text, self.dictation_format)
        # Reset anchors so future begin_streaming starts clean.
        self._committed_end = -1
        self._partial_end = -1
        # Revert current char format so subsequent typing is editor-default.
        default_cursor = self.editor.textCursor()
        default_cursor.setCharFormat(self._default_char_format())
        self.editor.setTextCursor(default_cursor)
```

If the file has a `_default_char_format` helper already (it should, from the editable-transcript slice), leave it alone. If not, make the `setCharFormat(self._default_char_format())` call into an inline `QTextCharFormat()` construction — see the existing commit_partial for the idiom.

Remove any residual references to `_partial_start` and `_partial_len` from `main_window.py` — a grep pass at the end of this task catches leftovers.

- [ ] **Step 6.5: Grep for leftover `_partial_start` / `_partial_len`**

Run: `git grep -n "_partial_start\|_partial_len" src/ui/main_window.py tests/unit/test_main_window.py`
Expected: no results (in the modified files). If the grep returns lines in `test_main_window.py` that reference the old names, update those tests to use `_committed_end` / `_partial_end` or rewrite via the public methods.

- [ ] **Step 6.6: Run the main_window tests**

Run: `python -m pytest tests/unit/test_main_window.py -v`
Expected: all tests pass on a working PyQt6 env. DLL collection error ⇒ document and proceed; downstream coverage via orchestrator + integration tests still exercises the commit semantics.

- [ ] **Step 6.7: Commit**

```bash
git add src/ui/main_window.py tests/unit/test_main_window.py
git commit -m "MainWindow: replace partial_start/len anchors with committed_end/partial_end + on_commit slot"
```

---

## Task 7: `main.py` — wire `commit_ready` → `window.on_commit`, inject `streaming` into orchestrator

**Why:** Without this, the new signals and the new orchestrator `streaming` kwarg aren't actually hooked up in the running app. No new tests — this is wiring code covered by the integration test in Task 8.

**Files:**
- Modify: `src/main.py`

- [ ] **Step 7.1: Inject `streaming` into the orchestrator construction**

Open `src/main.py`. Find the block that constructs `StreamingTranscriber` and `DictationOrchestrator`. Reorder and wire:

Locate the current construction. It looks roughly like:

```python
orchestrator = DictationOrchestrator(
    recorder=recorder,
    stt_client=stt,
    wedge=wedge,
    profiler=profiler,
    llm_client=llm,
)

window = MainWindow()
window.profiler = profiler
window.show()

streaming = StreamingTranscriber(recorder, stt, interval_ms=1500)
streaming.partial_ready.connect(window.update_partial)
```

Change it to construct `streaming` BEFORE the orchestrator (so the kwarg has a value), and connect the new `commit_ready` signal to the window:

```python
window = MainWindow()
window.profiler = profiler
window.show()

streaming = StreamingTranscriber(recorder, stt, interval_ms=1500)
streaming.partial_ready.connect(window.update_partial)
streaming.commit_ready.connect(window.on_commit)

orchestrator = DictationOrchestrator(
    recorder=recorder,
    stt_client=stt,
    wedge=wedge,
    profiler=profiler,
    llm_client=llm,
    streaming=streaming,
)
```

- [ ] **Step 7.2: Verify `on_stt_changed` still swaps the STT on both sides**

Scroll to `on_stt_changed`. It currently assigns `orchestrator.stt_client = new_client` and `streaming.stt_client = new_client`. The second assignment now flows through the `StreamingTranscriber.stt_client` setter (added in Task 4), which also updates `_splitter.stt_client`. No change needed — just confirm both lines are still present.

If you don't see `streaming.stt_client = new_client`, add it after the orchestrator line.

- [ ] **Step 7.3: Smoke-run the app import**

Run: `python -c "import src.main; print('main imports clean')"`
Expected: `main imports clean` (no exceptions). If PyQt6's DLL issue blocks the import, note — the integration test in Task 8 doesn't depend on importing `src.main`.

- [ ] **Step 7.4: Commit**

```bash
git add src/main.py
git commit -m "main: wire streaming.commit_ready to window.on_commit + inject streaming into orchestrator"
```

---

## Task 8: Integration test — end-to-end streaming commit pipeline

**Why:** The integration test asserts the whole commit/split pipeline works together — `CommitSplitter` feeding `MainWindow` via the signal contract, and the orchestrator reading the snapshot correctly on Stop. Catches wiring regressions that unit tests miss.

**Files:**
- Create: `tests/integration/test_streaming_pipeline.py`

- [ ] **Step 8.1: Check the integration test directory exists**

Run: `ls tests/integration/`
Expected: the directory exists (from earlier slices). If not: `mkdir -p tests/integration && touch tests/integration/__init__.py`.

- [ ] **Step 8.2: Write the failing integration test**

Create `tests/integration/test_streaming_pipeline.py`:

```python
"""End-to-end streaming commit/split with mock recorder + STT.

Drives the new pipeline without Qt / microphone / real model. Uses
CommitSplitter directly (Qt-independent) and exercises the orchestrator
Stop path through its public interface.
"""
import io
import wave

import numpy as np

from src.core.commit_splitter import CommitSplitter
from src.core.orchestrator import DictationOrchestrator


class ReplayRecorder:
    """Recorder double whose buffer grows over time under test control."""

    sample_rate = 16000
    channels = 1

    def __init__(self):
        self._samples = np.zeros(0, dtype=np.float32)

    def append(self, new_samples: np.ndarray) -> None:
        self._samples = np.concatenate([self._samples, new_samples])

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def get_sample_count(self) -> int:
        return int(self._samples.size)

    def get_wav_bytes_slice(self, start: int, end: int) -> bytes:
        if start < 0 or end < start or end > self._samples.size:
            raise ValueError(f"bad range: [{start}, {end}]")
        pcm = (self._samples[start:end] * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(pcm.tobytes())
        return buf.getvalue()

    def get_wav_bytes(self) -> bytes:
        return self.get_wav_bytes_slice(0, self._samples.size)


class ScriptedSTT:
    def __init__(self, script: list[str]):
        self._script = list(script)
        self.calls: list[int] = []

    def transcribe(self, wav_bytes: bytes) -> str:
        with wave.open(io.BytesIO(wav_bytes)) as wf:
            self.calls.append(wf.getnframes())
        if not self._script:
            return ""
        return self._script.pop(0)


def _tone(duration_s: float, amplitude: float = 0.3) -> np.ndarray:
    t = np.arange(int(16000 * duration_s)) / 16000
    return (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def _silence(duration_s: float) -> np.ndarray:
    return np.zeros(int(16000 * duration_s), dtype=np.float32)


def test_streaming_pipeline_two_commits_then_stop():
    recorder = ReplayRecorder()
    stt = ScriptedSTT([
        "the patient has a cough",    # first commit
        "and is febrile",             # partial after first commit
        "and is febrile today",       # second commit
        "normal exam",                # partial after second commit
        "and no acute findings",      # final remainder at Stop
    ])
    splitter = CommitSplitter(recorder=recorder, stt_client=stt)

    # Tick 1: record up to "patient has a cough" + long pause + partial tail.
    recorder.append(np.concatenate([_tone(2.5), _silence(0.8), _tone(1.0)]))
    r1 = splitter.process_tick()
    assert r1.commit_text.lower() == "the patient has a cough"
    assert "febrile" in r1.partial_text.lower()

    # Tick 2: more audio with another long pause — second commit.
    recorder.append(np.concatenate([_tone(1.5), _silence(0.8), _tone(0.8)]))
    r2 = splitter.process_tick()
    assert "febrile today" in r2.commit_text.lower()
    assert "normal exam" in r2.partial_text.lower()

    # Simulate Stop: a DictationOrchestrator wired with this splitter.
    class FakeStreaming:
        def __init__(self, splitter):
            self._splitter = splitter

        def get_committed_snapshot(self):
            return self._splitter.get_committed_snapshot()

    orch = DictationOrchestrator(
        recorder=recorder,
        stt_client=stt,
        wedge=object(),
        streaming=FakeStreaming(splitter),
    )
    orch.radiology_mode = False  # isolate the assertion from lexicon swaps
    final = orch.handle_trigger_up(mode="inapp")
    # Full text is committed chunks + final remainder, post-processed.
    lowered = final.lower()
    assert "cough" in lowered
    assert "febrile today" in lowered
    assert "no acute findings" in lowered


def test_streaming_pipeline_no_commits_falls_back_to_whole_buffer():
    recorder = ReplayRecorder()
    recorder.append(_tone(2.0))  # one short tone, no pauses
    stt = ScriptedSTT(["hello"])
    splitter = CommitSplitter(recorder=recorder, stt_client=stt)

    r = splitter.process_tick()
    assert r.commit_text is None
    assert r.partial_text == "hello"

    # Stop with no commits: orchestrator uses whole-buffer path.
    class FakeStreaming:
        def __init__(self, splitter):
            self._splitter = splitter

        def get_committed_snapshot(self):
            return self._splitter.get_committed_snapshot()

    stt_for_stop = ScriptedSTT(["hello again"])
    orch = DictationOrchestrator(
        recorder=recorder,
        stt_client=stt_for_stop,
        wedge=object(),
        streaming=FakeStreaming(splitter),
    )
    orch.radiology_mode = False
    final = orch.handle_trigger_up(mode="inapp")
    assert "hello again" in final.lower()
```

- [ ] **Step 8.3: Run the integration test**

Run: `python -m pytest tests/integration/test_streaming_pipeline.py -v`
Expected: both tests pass. Runtime ~1 s.

- [ ] **Step 8.4: Commit**

```bash
git add tests/integration/test_streaming_pipeline.py
git commit -m "Streaming: integration test for commit/split + orchestrator Stop"
```

---

## Task 9: New profiling scenario — `scenario_streaming_commit`

**Why:** Without this, the next profiling report won't show the win from this slice — we'd be looking at the old `streaming_tick` number with no comparison. Adding a paired scenario makes the before/after obvious.

**Files:**
- Modify: `tools/profiling/scenarios.py`
- Modify: `tools/profile_pipeline.py` — register the new scenario.
- Modify: `tests/unit/test_profiling_scenarios.py`

- [ ] **Step 9.1: Add a failing test**

Open `tests/unit/test_profiling_scenarios.py`. Append:

```python
def test_scenario_streaming_commit_runs_three_buffer_sizes(tmp_path):
    from tools.profiling.scenarios import scenario_streaming_commit
    # Seed clip WAVs (the scenario reads from clips_dir for any scenarios
    # that need them, but streaming_commit synthesizes its own audio
    # internally — still, ctx has a clips_dir so keep parity with siblings).
    result = scenario_streaming_commit(_ctx(tmp_path, iterations=2))
    assert result.name == "streaming_commit"
    assert "5s" in result.timings_ms
    assert "15s" in result.timings_ms
    assert "30s" in result.timings_ms
    for samples in result.timings_ms.values():
        assert len(samples) == 2
```

- [ ] **Step 9.2: Run the test — expect ImportError**

Run: `python -m pytest tests/unit/test_profiling_scenarios.py -v -k "streaming_commit"`
Expected: `ImportError: cannot import name 'scenario_streaming_commit' from 'tools.profiling.scenarios'`.

- [ ] **Step 9.3: Add the scenario**

Open `tools/profiling/scenarios.py`. Add the following at the end of the file:

```python
def _tone_silence_pattern(total_s: float) -> bytes:
    """Synthesize a tone-silence-tone-... pattern WAV.

    440 Hz sine at amplitude 0.3, alternating 2.5 s tones with 600 ms
    silences, clipped to `total_s` total duration. Ensures VAD has
    commit points to find at roughly every 3 s.
    """
    import io

    import numpy as np

    sr = 16000
    chunks: list[np.ndarray] = []
    remaining = total_s
    tone_len = 2.5
    silence_len = 0.6
    t = np.arange(int(sr * tone_len)) / sr
    tone = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    silence = np.zeros(int(sr * silence_len), dtype=np.float32)
    while remaining > 0:
        if remaining >= tone_len:
            chunks.append(tone)
            remaining -= tone_len
        else:
            partial = (0.3 * np.sin(2 * np.pi * 440 * np.arange(int(sr * remaining)) / sr)).astype(np.float32)
            chunks.append(partial)
            remaining = 0
            break
        if remaining >= silence_len:
            chunks.append(silence)
            remaining -= silence_len
        else:
            chunks.append(np.zeros(int(sr * remaining), dtype=np.float32))
            remaining = 0
    all_samples = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    pcm = (all_samples * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def scenario_streaming_commit(ctx: ProfilingContext) -> ScenarioResult:
    """Per-tick cost of the NEW streaming path (CommitSplitter).

    Uses a tone-silence-tone audio pattern so VAD has commit points to
    find. Measures one `process_tick()` call per iteration on 5 / 15 /
    30 s buffers. Paired with `scenario_streaming_tick` for before/after
    comparison in the report.
    """
    from src.core.commit_splitter import CommitSplitter
    from tools.profiling.mocks import MockRecorder

    stt = ctx.stt_factory()
    if hasattr(stt, "warm"):
        stt.warm()

    spans: dict[str, list[float]] = {"5s": [], "15s": [], "30s": []}
    for label, duration_s in (("5s", 5.0), ("15s", 15.0), ("30s", 30.0)):
        wav = _tone_silence_pattern(duration_s)
        for _ in range(ctx.iterations):
            # Fresh recorder + splitter per iteration — commits from a
            # prior iteration mustn't skew the current measurement.
            recorder = MockRecorder(audio_bytes=wav)
            # Splitter expects recorder.get_sample_count + get_wav_bytes_slice.
            # Teach MockRecorder those by piggy-backing on the WAV bytes it
            # already owns.
            recorder.get_sample_count = lambda w=wav: _wav_sample_count(w)
            recorder.get_wav_bytes_slice = lambda s, e, w=wav: _wav_slice(w, s, e)
            splitter = CommitSplitter(recorder=recorder, stt_client=stt)
            t0 = time.perf_counter()
            splitter.process_tick()
            spans[label].append((time.perf_counter() - t0) * 1000)
    return ScenarioResult(
        name="streaming_commit",
        params={"iterations_per_size": ctx.iterations},
        timings_ms=spans,
    )


def _wav_sample_count(wav_bytes: bytes) -> int:
    import io

    with wave.open(io.BytesIO(wav_bytes)) as wf:
        return wf.getnframes()


def _wav_slice(wav_bytes: bytes, start_sample: int, end_sample: int) -> bytes:
    import io

    with wave.open(io.BytesIO(wav_bytes)) as wf:
        if start_sample < 0 or end_sample < start_sample or end_sample > wf.getnframes():
            raise ValueError(f"bad slice [{start_sample}, {end_sample}]")
        wf.setpos(start_sample)
        frames = wf.readframes(end_sample - start_sample)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(frames)
    return buf.getvalue()
```

- [ ] **Step 9.4: Register the scenario in the CLI**

Open `tools/profile_pipeline.py`. Add the import and add the scenario to the `bench` list and the `_DISCOVERY_SCENARIOS` set.

Change the scenarios import:

```python
from tools.profiling.scenarios import (
    scenario_cold_import,
    scenario_full_pipeline,
    scenario_sensevoice_warm,
    scenario_stt_hot_path,
    scenario_streaming_commit,
    scenario_streaming_tick,
    scenario_text_post_processing,
)
```

Change `_DISCOVERY_SCENARIOS`:

```python
_DISCOVERY_SCENARIOS = {
    "stt_hot_path",
    "full_pipeline",
    "streaming_tick",
    "streaming_commit",
    "text_post_processing",
}
```

Add the new scenario to `bench`:

```python
    bench = [
        ("cold_import", scenario_cold_import, 1),
        ("sensevoice_warm", scenario_sensevoice_warm, max(1, args.iterations)),
        ("stt_hot_path", scenario_stt_hot_path, args.iterations),
        ("full_pipeline", scenario_full_pipeline, args.iterations),
        ("streaming_tick", scenario_streaming_tick, args.iterations),
        ("streaming_commit", scenario_streaming_commit, args.iterations),
        ("text_post_processing", scenario_text_post_processing, args.iterations_text),
    ]
```

- [ ] **Step 9.5: Run the scenario unit test**

Run: `python -m pytest tests/unit/test_profiling_scenarios.py -v`
Expected: all tests pass (old + new).

- [ ] **Step 9.6: Smoke-test the CLI end-to-end**

Run: `python -m pytest tests/unit/test_profile_pipeline_dryrun.py -v`
Expected: the dry-run smoke test still passes and the report contains `streaming_commit` as a row (the smoke test's existing assertion checks all scenario names appear; `streaming_commit` is picked up automatically since its name is in the `bench` list).

Strengthen the smoke test to assert the new name is present. Open `tests/unit/test_profile_pipeline_dryrun.py` and add `"streaming_commit"` to the list in the assertion loop:

```python
    for name in (
        "cold_import",
        "sensevoice_warm",
        "stt_hot_path",
        "full_pipeline",
        "streaming_tick",
        "streaming_commit",
        "text_post_processing",
    ):
        assert name in content, f"{name} missing from report"
```

Re-run the smoke test: `python -m pytest tests/unit/test_profile_pipeline_dryrun.py -v`
Expected: passes.

- [ ] **Step 9.7: Commit**

```bash
git add tools/profiling/scenarios.py tools/profile_pipeline.py tests/unit/test_profiling_scenarios.py tests/unit/test_profile_pipeline_dryrun.py
git commit -m "Profiling: add scenario_streaming_commit (paired with streaming_tick)"
```

---

## Task 10: Run the profiling harness + commit the new report

**Why:** Per the standing plan template, every plan ends with a profiling pass. This one's profiling pass is a live run of the tool — the before/after comparison is the deliverable.

**Files:**
- Creates: `docs/superpowers/profiling/<timestamp>-profile.md` (committed).
- Creates trace HTMLs under `docs/superpowers/profiling/<timestamp>-profile/` (gitignored).

- [ ] **Step 10.1: Run the harness**

Run: `python -m tools.profile_pipeline`
Expected:
- Clips already exist from the prior run (Task 10 of the previous plan) — `ensure_clips` is a no-op.
- Each scenario prints its timing/discovery pass line, including the new `streaming_commit`.
- Final line: `Report: docs\superpowers\profiling\2026-MM-DD-HHMM-profile.md`.

- [ ] **Step 10.2: Spot-check the new report**

Open the generated markdown. Verify:
- Both `streaming_tick` and `streaming_commit` rows are present.
- `streaming_commit`'s p95 at the 30 s row is substantially lower than `streaming_tick`'s p95 at the 30 s row. Target: `streaming_commit` p95 ≤ 400 ms; `streaming_tick` p95 unchanged at ~1.5 s (it's the baseline regression guard).
- If `streaming_commit` is NOT faster than `streaming_tick`, something is wrong — either VAD isn't firing on the synthesized pattern (check `scenario_streaming_commit`'s `_tone_silence_pattern` against `find_commit_point` expectations), or `process_tick` is transcribing more than expected (check the `get_wav_bytes_slice` calls made per tick). Stop and investigate before committing.

- [ ] **Step 10.3: Commit the markdown report**

```bash
git add docs/superpowers/profiling/*.md
git commit -m "Profiling: post-streaming-commit report (streaming_commit vs streaming_tick)"
```

Traces are gitignored from the earlier .gitignore rule — `git status` after the commit should show nothing stray.

---

## Task 11: Dead-code + readability sweep

**Why:** Standing plan-template closer.

**Files:**
- Potentially modify: any of `src/core/streaming.py`, `src/core/commit_splitter.py`, `src/core/vad.py`, `src/ui/main_window.py`, `src/core/orchestrator.py`, `src/hardware/recorder.py`, `src/main.py`, or the profiling scenario additions.

- [ ] **Step 11.1: Run the full test suite (minus the known Qt-DLL blockers)**

Run: `python -m pytest tests/ --ignore=tests/unit/test_global_hotkey.py --ignore=tests/unit/test_main_window.py --ignore=tests/unit/test_mic_listener.py --ignore=tests/unit/test_streaming.py -q`
Expected: all tests pass, same count as before this plan + new tests from Tasks 1, 2, 3, 5, 8, 9.

If PyQt6 has been fixed in the meantime and the previously-blocked test files pass, run the full `pytest tests/ -q` instead.

- [ ] **Step 11.2: grep for dead references**

Run: `git grep -n "_partial_start\|_partial_len" -- ':!docs/'`
Expected: no hits in `src/` or `tests/` (only documentation mentions might remain in `docs/superpowers/`, which is historical — fine).

If hits appear, address them (rename / remove).

- [ ] **Step 11.3: File size budget check**

Run: `wc -l src/core/streaming.py src/core/commit_splitter.py src/core/vad.py src/core/orchestrator.py src/ui/main_window.py src/hardware/recorder.py`
Expected: each file under 300 lines except `main_window.py` (which is already large from prior slices — ok to exceed, but if it's now over 500 lines, add a TODO-comment-free follow-up note in your head: "extract DictationEditor in a future slice" — do NOT refactor it in this slice).

- [ ] **Step 11.4: Read each new/touched file top-to-bottom**

Open each file listed in Step 11.3 plus `tools/profiling/scenarios.py`. Look specifically for:
- Imports nothing uses.
- Functions defined but never called (remove or note as intentional-hook-with-comment — preferably remove).
- Multiline comments that restate the next line of code (remove).
- Left-over prints / `logger.debug` that were only useful mid-implementation (remove the ones that don't add audit value).

- [ ] **Step 11.5: Commit any cleanups**

If Steps 11.2 / 11.4 produced edits:

```bash
git add <edited files>
git commit -m "Streaming: dead-code + readability sweep"
```

If nothing changed, skip this commit — no empty commits.

---

## Self-review — spec coverage and consistency

Spec requirements → implementing tasks:

- Spec §Architecture, `src/core/vad.py` → Task 1.
- Spec §Architecture, `AudioRecorder.get_wav_bytes_slice` / `get_sample_count` → Task 2.
- Spec §Architecture, state lives on StreamingTranscriber — implementation puts it on an owned `CommitSplitter` that StreamingTranscriber delegates to → Tasks 3 + 4. The Qt wrapper still exposes `get_committed_snapshot()` per the spec; internal storage is an implementation detail.
- Spec §Architecture, `commit_ready` signal → Task 4.
- Spec §Architecture, `MainWindow` anchors and `on_commit` slot → Task 6.
- Spec §Architecture, orchestrator Stop-path read of committed snapshot → Task 5.
- Spec §Architecture, `main.py` wiring → Task 7.
- Spec §Data flow → Tasks 3, 6, 7 together; integration verification in Task 8.
- Spec §Error handling — commit transcribe fail / empty, partial fail, VAD-never-commits, 30 s cap, Stop during in-flight, short-dictation fallback → covered by: Task 3 tests (commit fail/empty), Task 1 tests (VAD fallbacks), Task 5 tests (no-commits path), Task 4 tests (stop during in-flight).
- Spec §Back-compatibility, orchestrator still works with no streaming kwarg → Task 5 test `test_orchestrator_without_streaming_handle_works_as_today`.
- Spec §Testing, every listed unit / integration / profiling test → distributed across Tasks 1-9.
- Spec §Profiling pass closing step → Task 10.
- Spec §Dead-code sweep closing step → Task 11.

Type consistency across tasks:
- `TickResult(commit_text, partial_text)` — defined in Task 3; used by Task 4 (streaming) and Task 9 (profiling scenario uses its return implicitly). ✓
- `CommitSplitter(recorder, stt_client, sample_rate, min_partial_s)` — defined Task 3; constructed in Task 4, Task 8, Task 9. ✓
- `StreamingTranscriber.get_committed_snapshot() -> tuple[list[str], int]` — defined in Task 4 (delegates to splitter); consumed in Task 5. ✓
- `DictationOrchestrator.__init__(..., streaming=None)` — defined in Task 5; wired in Task 7. ✓
- `MainWindow.on_commit(text: str) -> None` — defined Task 6; wired in Task 7. ✓
- `AudioRecorder.get_sample_count() / get_wav_bytes_slice(start, end)` — defined Task 2; consumed in Tasks 3, 5, 9. ✓
- `find_commit_point(samples, sample_rate, ...)` signature — defined Task 1; called in Task 3. ✓

No placeholders. No "similar to Task N." All code steps contain complete code.
