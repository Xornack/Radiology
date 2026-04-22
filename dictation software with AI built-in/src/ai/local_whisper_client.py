import io
import threading
import wave
import numpy as np
from loguru import logger


class LocalWhisperClient:
    """
    In-process STT using faster-whisper. No server needed.

    Drop-in replacement for WhisperClient (same `transcribe(bytes) -> str` API).
    The model loads lazily on first transcribe() call; call warm() to preload
    it in a background thread so the first dictation isn't delayed.
    """
    # Whisper is fast enough to drive 1.5s streaming ticks.
    supports_streaming: bool = True

    def __init__(
        self,
        model_size: str = "base.en",
        device: str = "auto",
        compute_type: str = "auto",
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._load_lock = threading.Lock()

    def _load_model(self):
        with self._load_lock:
            if self._model is None:
                logger.info(
                    f"Loading faster-whisper model '{self.model_size}' "
                    f"(device={self.device}, compute_type={self.compute_type})..."
                )
                # Deferred import: heavy dependency, only needed when local mode is used
                from faster_whisper import WhisperModel
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )
                logger.info("Whisper model loaded.")
            return self._model

    def warm(self):
        """Preload the model in a background thread. Safe to call multiple times."""
        try:
            self._load_model()
        except Exception as e:
            logger.error(f"Failed to preload Whisper model: {e}")

    def transcribe(self, audio_bytes: bytes) -> str:
        """
        Decodes 16-bit mono 16kHz WAV bytes and runs them through faster-whisper.
        Returns the transcript, or empty string on any failure.
        """
        if not audio_bytes:
            return ""
        try:
            with wave.open(io.BytesIO(audio_bytes)) as wf:
                if (
                    wf.getsampwidth() != 2
                    or wf.getnchannels() != 1
                    or wf.getframerate() != 16000
                ):
                    logger.error(
                        f"Unsupported WAV format: {wf.getnchannels()}ch, "
                        f"{wf.getsampwidth()*8}-bit, {wf.getframerate()}Hz — "
                        f"expected mono 16-bit 16kHz"
                    )
                    return ""
                frames = wf.readframes(wf.getnframes())

            if not frames:
                return ""

            audio = (
                np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            )

            try:
                model = self._load_model()
                segments, _info = model.transcribe(
                    audio,
                    beam_size=1,
                    language="en",
                    vad_filter=True,
                )
                return " ".join(seg.text.strip() for seg in segments).strip()
            except Exception as e:
                # CUDA runtime errors (missing cuBLAS/cuDNN) only surface at
                # inference time — fall back to CPU and retry once.
                msg = str(e).lower()
                cuda_failed = (
                    self.device == "cuda"
                    and ("cuda" in msg or "cublas" in msg or "cudnn" in msg)
                )
                if cuda_failed:
                    logger.warning(
                        f"CUDA inference failed ({e}); falling back to CPU+int8."
                    )
                    with self._load_lock:
                        self.device = "cpu"
                        self.compute_type = "int8"
                        self._model = None
                    model = self._load_model()
                    segments, _info = model.transcribe(
                        audio, beam_size=1, language="en", vad_filter=True,
                    )
                    return " ".join(seg.text.strip() for seg in segments).strip()
                raise
        except Exception as e:
            logger.error(f"Local Whisper transcription failed: {e}")
            return ""
