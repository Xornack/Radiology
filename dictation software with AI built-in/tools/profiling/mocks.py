"""Lightweight test doubles for the profiling harness.

MockRecorder feeds pre-loaded WAV bytes to scenarios that need to exercise
the pipeline without a real microphone. MockWedge captures keystroke
targets without touching Win32. FixedLatencySTT is the `--dry-run` STT
substitute — it sleeps a fixed amount and returns a canned string so the
harness itself can be smoke-tested end-to-end without loading SenseVoice.
"""
import time
from typing import Optional


class MockRecorder:
    """Returns pre-loaded WAV bytes; start/stop/set_device are no-ops."""

    def __init__(self, audio_bytes: bytes):
        self._audio_bytes = audio_bytes
        self.device: Optional[int] = None

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def set_device(self, device_index: Optional[int]) -> None:
        pass

    def get_wav_bytes(self) -> bytes:
        return self._audio_bytes


class MockWedge:
    """Records calls to `type_text` without touching Win32."""

    def __init__(self) -> None:
        self.last_text: Optional[str] = None
        self.call_count: int = 0

    def type_text(self, text: str) -> None:
        self.last_text = text
        self.call_count += 1


class FixedLatencySTT:
    """Deterministic STT stand-in for `--dry-run` harness runs.

    `transcribe` sleeps `latency_ms` to model the dominant cost of a real
    STT call. `warm` sleeps `warm_latency_ms` separately so the dry-run
    sensevoice_warm scenario produces plausible timing data without
    loading a 100 MB model.
    """

    supports_streaming: bool = True

    def __init__(
        self,
        latency_ms: int = 200,
        warm_latency_ms: int = 50,
        text: str = "mock transcription",
    ):
        self._latency_s = latency_ms / 1000.0
        self._warm_s = warm_latency_ms / 1000.0
        self._text = text

    def warm(self) -> None:
        time.sleep(self._warm_s)

    def transcribe(self, audio_bytes: bytes) -> str:
        time.sleep(self._latency_s)
        return self._text
