"""On-device STT using Vosk (Kaldi-based).

Old-school GMM/DNN ASR — completely different lineage from Whisper, Gemma,
and Parakeet. Very lightweight: the small English model is ~50 MB and runs
comfortably on modest CPUs. No GPU required.

Requires the optional `[vosk]` extra:
    pip install -e '.[vosk]'

Vosk models are NOT auto-downloaded — grab one from https://alphacephei.com/vosk/models
(e.g. `vosk-model-small-en-us-0.15`) and set `VOSK_MODEL_PATH` to the unpacked
directory, or pass model_path to the constructor.
"""
import io
import json
import threading
import wave
from loguru import logger


class VoskSTTClient:
    """STT via `vosk`. Point it at an unpacked Vosk model directory.

    Reads WAV bytes directly (Vosk accepts 16-bit mono PCM), buffers them
    through a KaldiRecognizer, and returns the `FinalResult()` JSON's text.
    """

    # Vosk on CPU is fast enough for live partials; it's designed for
    # real-time streaming recognition.
    supports_streaming: bool = True

    def __init__(self, model_path: str):
        self.model_path = model_path
        self._model = None
        self._load_lock = threading.Lock()

    def _load(self):
        with self._load_lock:
            if self._model is None:
                logger.info(f"Loading Vosk model from '{self.model_path}'...")
                import vosk
                self._model = vosk.Model(self.model_path)
                logger.info("Vosk model loaded.")
            return self._model

    def warm(self):
        try:
            self._load()
        except Exception as e:
            logger.error(f"Failed to preload Vosk model: {e}")

    def transcribe(self, audio_bytes: bytes) -> str:
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
                        f"Vosk expects mono 16-bit 16kHz WAV; got "
                        f"{wf.getnchannels()}ch {wf.getsampwidth() * 8}-bit "
                        f"{wf.getframerate()}Hz"
                    )
                    return ""
                pcm_bytes = wf.readframes(wf.getnframes())
            if not pcm_bytes:
                return ""

            model = self._load()
            import vosk
            rec = vosk.KaldiRecognizer(model, 16000)
            rec.AcceptWaveform(pcm_bytes)
            final = json.loads(rec.FinalResult())
            return final.get("text", "").strip()
        except Exception as e:
            logger.error(f"Vosk transcription failed: {e}")
            return ""
