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

        # Buffer can shrink between get_sample_count and get_wav_bytes_slice
        # if the recorder is restarted mid-tick (UI restart race). Swallow
        # the resulting ValueError and skip this tick — the next one will
        # realign.
        try:
            partial_wav = self.recorder.get_wav_bytes_slice(
                self._commit_sample_idx, end_sample
            )
        except ValueError as e:
            logger.warning(f"Skipping tick due to buffer boundary shift: {e}")
            return TickResult()
        partial_samples_arr = _decode_wav_to_float32(partial_wav)

        commit_local_idx = find_commit_point(
            partial_samples_arr, sample_rate=self.sample_rate
        )

        commit_text: Optional[str] = None
        if commit_local_idx is not None and commit_local_idx > 0:
            commit_end_global = self._commit_sample_idx + commit_local_idx
            try:
                commit_wav = self.recorder.get_wav_bytes_slice(
                    self._commit_sample_idx, commit_end_global
                )
            except ValueError as e:
                logger.warning(f"Skipping commit due to buffer boundary shift: {e}")
                return TickResult()
            try:
                raw = self.stt_client.transcribe(commit_wav)
            except Exception as e:
                logger.error(f"Commit transcribe failed, skipping commit: {e}")
                raw = ""
            if raw:
                # capitalize_first=False: commit chunks are mid-sentence
                # relative to the final concatenated text. The orchestrator's
                # Stop-path post-processing decides casing from editor context.
                commit_text = apply_punctuation(
                    raw,
                    capitalize_first=False,
                    strip_inferred=getattr(
                        self.stt_client, "emits_punctuation", False
                    ) is not True,
                )
                self._committed_text.append(commit_text)
                self._commit_sample_idx = commit_end_global

        partial_end = end_sample
        partial_start = self._commit_sample_idx
        if partial_end - partial_start <= 0:
            return TickResult(commit_text=commit_text, partial_text=None)

        try:
            remainder_wav = self.recorder.get_wav_bytes_slice(
                partial_start, partial_end
            )
        except ValueError as e:
            logger.warning(f"Skipping partial due to buffer boundary shift: {e}")
            return TickResult(commit_text=commit_text, partial_text=None)
        try:
            raw = self.stt_client.transcribe(remainder_wav)
        except Exception as e:
            logger.error(f"Partial transcribe failed: {e}")
            raw = ""
        partial_text = (
            apply_punctuation(
                raw,
                capitalize_first=False,
                strip_inferred=not getattr(
                    self.stt_client, "emits_punctuation", False
                ),
            )
            if raw
            else None
        )

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
