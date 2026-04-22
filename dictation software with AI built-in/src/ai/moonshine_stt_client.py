"""On-device STT using Useful Sensors' Moonshine.

Dedicated ASR model like Whisper but optimized for fast CPU inference — a
reasonable alternative when Whisper-base isn't quite fast enough and Gemma
is way too heavy. Two sizes: tiny (~27M params) and base (~61M params).

Requires the optional `[moonshine]` extra:
    pip install -e '.[moonshine]'
"""
import io
import threading
import wave
import numpy as np
from loguru import logger


class MoonshineSTTClient:
    """STT via `useful-moonshine`. Takes the same bytes-in, text-out shape as
    WhisperClient so the orchestrator/streaming code is unchanged.

    model: "moonshine/tiny" or "moonshine/base"
    """

    # Moonshine is fast enough for live partials on CPU (~5× faster than
    # Whisper-tiny on the same hardware), so streaming is enabled.
    supports_streaming: bool = True

    def __init__(self, model: str = "moonshine/base"):
        self.model_name = model
        self._model = None
        self._load_lock = threading.Lock()

    def _load(self):
        with self._load_lock:
            if self._model is None:
                logger.info(f"Loading Moonshine model '{self.model_name}'...")
                moonshine = _import_moonshine()
                # Some versions preload via load_model, others are pure
                # module-level functions; we hold a reference so subsequent
                # transcribe() calls don't re-initialize.
                loader = getattr(moonshine, "load_model", None)
                self._model = loader(self.model_name) if loader else moonshine
                logger.info("Moonshine model loaded.")
            return self._model

    def warm(self):
        try:
            self._load()
        except Exception as e:
            logger.error(f"Failed to preload Moonshine model: {e}")

    def transcribe(self, audio_bytes: bytes) -> str:
        if not audio_bytes:
            return ""
        try:
            audio = _decode_wav_to_float32(audio_bytes)
            if audio is None or audio.size == 0:
                return ""
            self._load()
            moonshine = _import_moonshine()
            # `transcribe` accepts a numpy float32 array at 16kHz and returns
            # a list of transcribed segments. Join into a single string so
            # callers see the same shape as WhisperClient.transcribe().
            segments = moonshine.transcribe(audio, self.model_name)
            if isinstance(segments, (list, tuple)):
                return " ".join(s.strip() for s in segments).strip()
            return str(segments).strip()
        except Exception as e:
            logger.error(f"Moonshine transcription failed: {e}")
            return ""


def _import_moonshine():
    """Import either the ONNX or PyTorch Moonshine package, whichever is present.

    `useful-moonshine-onnx` imports as `moonshine_onnx`; the torch flavor
    imports as `moonshine`. Both expose the same `transcribe()` top-level.
    """
    try:
        import moonshine_onnx
        return moonshine_onnx
    except ImportError:
        import moonshine
        return moonshine


def _decode_wav_to_float32(audio_bytes: bytes):
    """Pull int16 mono 16kHz PCM out of our recorder's WAV bytes → float32.

    Returns None on format mismatch so transcribe() can short-circuit.
    """
    with wave.open(io.BytesIO(audio_bytes)) as wf:
        if (
            wf.getsampwidth() != 2
            or wf.getnchannels() != 1
            or wf.getframerate() != 16000
        ):
            logger.error(
                f"Moonshine expects mono 16-bit 16kHz WAV; got "
                f"{wf.getnchannels()}ch {wf.getsampwidth() * 8}-bit "
                f"{wf.getframerate()}Hz"
            )
            return None
        frames = wf.readframes(wf.getnframes())
    if not frames:
        return np.zeros(0, dtype=np.float32)
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
