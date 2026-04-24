"""Shared scaffolding for the on-device STT clients.

Why this module exists: before consolidation, six STT clients reimplemented
the same four patterns — lazy-load lock, warm() best-effort, empty-audio
guard, exception-to-empty-string on failure — plus three of them carried
byte-identical WAV decoders. Diverging copies would silently miss bug fixes,
so the common parts live here.
"""
import io
import threading
import wave
from abc import ABC, abstractmethod
from typing import Any, Optional

import numpy as np
from loguru import logger


class STTError(Exception):
    """Non-transient STT failure. Not used for silence (empty audio → "")."""


def decode_wav_to_float32(
    wav_bytes: bytes,
    *,
    backend_name: str = "STT",
    expected_rate: int = 16000,
    expected_channels: int = 1,
    expected_sampwidth: int = 2,
) -> Optional[np.ndarray]:
    """Validate and decode a recorder-format WAV into a [-1, 1] float32 array.

    Returns None on format mismatch so callers can short-circuit to "";
    returns a zero-length array on an empty frames payload.
    """
    with wave.open(io.BytesIO(wav_bytes)) as wf:
        if (
            wf.getsampwidth() != expected_sampwidth
            or wf.getnchannels() != expected_channels
            or wf.getframerate() != expected_rate
        ):
            logger.error(
                f"{backend_name} expects mono {expected_sampwidth * 8}-bit "
                f"{expected_rate}Hz WAV; got {wf.getnchannels()}ch "
                f"{wf.getsampwidth() * 8}-bit {wf.getframerate()}Hz"
            )
            return None
        frames = wf.readframes(wf.getnframes())
    if not frames:
        return np.zeros(0, dtype=np.float32)
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


def read_wav_raw_frames(
    wav_bytes: bytes,
    *,
    backend_name: str = "STT",
    expected_rate: int = 16000,
    expected_channels: int = 1,
    expected_sampwidth: int = 2,
) -> Optional[bytes]:
    """Same validation as decode_wav_to_float32 but returns the raw int16
    frames. For engines like Vosk that want PCM bytes, not float32."""
    with wave.open(io.BytesIO(wav_bytes)) as wf:
        if (
            wf.getsampwidth() != expected_sampwidth
            or wf.getnchannels() != expected_channels
            or wf.getframerate() != expected_rate
        ):
            logger.error(
                f"{backend_name} expects mono {expected_sampwidth * 8}-bit "
                f"{expected_rate}Hz WAV; got {wf.getnchannels()}ch "
                f"{wf.getsampwidth() * 8}-bit {wf.getframerate()}Hz"
            )
            return None
        return wf.readframes(wf.getnframes())


class BaseSTTClient(ABC):
    """Shared scaffolding for on-device STT clients.

    Handles the empty-audio guard, lazy-load lock, warm() best-effort, and
    exception-to-empty-string contract so subclasses only write the bits
    that differ between engines.

    Subclasses must set:
      - `name`: short log-friendly engine name.
      - `supports_streaming`: whether this engine is fast enough to drive
        the 1.5s streaming ticks.
    And must implement:
      - `_load_impl()`: one-shot model load; result is cached in `self._model`.
      - `_transcribe(audio_bytes)`: inference on guaranteed-non-empty audio.
    """

    name: str = "STT"
    supports_streaming: bool = False
    # True when the engine already emits real punctuation glyphs (MedASR),
    # so the post-processing pipeline must skip its Whisper-style
    # punctuation-stripping pass. Default False: Whisper + SenseVoice rely
    # on the stripper to erase auto-inferred commas/periods that the
    # radiologist didn't dictate.
    emits_punctuation: bool = False

    def __init__(self) -> None:
        self._model: Any = None
        self._load_lock = threading.Lock()

    def _load_locked(self) -> Any:
        """Load under an already-held `_load_lock`. Subclasses that need to
        reset+reload atomically (e.g. CUDA→CPU fallback) call this from
        inside their own `with self._load_lock:` block."""
        if self._model is None:
            self._model = self._load_impl()
        return self._model

    def _load(self) -> Any:
        with self._load_lock:
            return self._load_locked()

    @abstractmethod
    def _load_impl(self) -> Any:
        """Return a fully-loaded model. Run at most once per process."""

    def warm(self) -> None:
        """Preload in a background thread. Best-effort — a load failure is
        logged but not re-raised so the UI warm-up sweep stays resilient."""
        try:
            self._load()
        except Exception as e:
            logger.error(f"Failed to preload {self.name} model: {e}")

    def transcribe(self, audio_bytes: bytes) -> str:
        """Run transcription. "" on empty audio or any inference failure so
        the dictation pipeline degrades gracefully rather than crashing
        the UI handler."""
        if not audio_bytes:
            return ""
        try:
            return self._transcribe(audio_bytes)
        except Exception as e:
            logger.error(f"{self.name} transcription failed: {e}")
            return ""

    @abstractmethod
    def _transcribe(self, audio_bytes: bytes) -> str:
        """Perform inference. Caller guarantees non-empty audio and wraps
        exceptions; subclasses can raise freely."""
