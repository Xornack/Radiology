"""On-device STT using NVIDIA's Parakeet-TDT via the NeMo toolkit.

Transducer-architecture ASR — different family from Whisper (encoder-decoder)
and Gemma (LLM). Known for very fast GPU inference and excellent accuracy.
CPU works but is much slower; GPU strongly recommended.

Requires the optional `[parakeet]` extra:
    pip install -e '.[parakeet]'

NeMo is a large install (~1 GB+) that pulls in pytorch-lightning, hydra-core,
and other heavy deps, which is why it's gated behind an extra.
"""
import os
import tempfile
import threading
from loguru import logger


class ParakeetSTTClient:
    """STT via `nemo_toolkit[asr]`. Same transcribe(bytes) -> str interface.

    model: e.g. "nvidia/parakeet-tdt-0.6b-v2" (default) or "nvidia/parakeet-tdt_ctc-110m".
    """

    # Parakeet on GPU is fast enough for live partials. We don't toggle this
    # by device though — users can pick whisper-local-cpu if they need CPU.
    supports_streaming: bool = True

    def __init__(self, model: str = "nvidia/parakeet-tdt-0.6b-v2"):
        self.model_name = model
        self._model = None
        self._load_lock = threading.Lock()

    def _load(self):
        with self._load_lock:
            if self._model is None:
                logger.info(f"Loading Parakeet model '{self.model_name}'...")
                import nemo.collections.asr as nemo_asr
                self._model = nemo_asr.models.ASRModel.from_pretrained(
                    model_name=self.model_name
                )
                logger.info("Parakeet model loaded.")
            return self._model

    def warm(self):
        try:
            self._load()
        except Exception as e:
            logger.error(f"Failed to preload Parakeet model: {e}")

    def transcribe(self, audio_bytes: bytes) -> str:
        if not audio_bytes:
            return ""
        # NeMo's transcribe() API is file-path oriented; write the WAV bytes
        # to a temp file so we don't have to reach into the lower-level
        # frame-by-frame interface just to avoid a disk round-trip.
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False
            ) as tf:
                tf.write(audio_bytes)
                temp_path = tf.name
            model = self._load()
            results = model.transcribe([temp_path])
            # NeMo ASRModel.transcribe returns either a list of strings or a
            # list of Hypothesis objects depending on the model/version.
            if not results:
                return ""
            first = results[0]
            text = getattr(first, "text", first)
            return str(text).strip()
        except Exception as e:
            logger.error(f"Parakeet transcription failed: {e}")
            return ""
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError as e:
                    logger.warning(f"Failed to clean up Parakeet temp WAV: {e}")
