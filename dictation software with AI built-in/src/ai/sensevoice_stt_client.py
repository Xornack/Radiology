"""On-device STT using Alibaba's SenseVoice via the FunASR framework.

Small multilingual ASR (~100M params) with built-in language detection,
emotion classification, and audio-event tagging. Fast on CPU, very fast
on GPU. The tagging features are interesting for future clinical cues
(e.g. detecting "stressed" speech during emergent dictations) but for now
we only consume the plain transcription text.

Requires the optional `[sensevoice]` extra:
    pip install -e '.[sensevoice]'
"""
import io
import threading
import wave
import re
import numpy as np
from loguru import logger


class SenseVoiceSTTClient:
    """STT via `funasr` AutoModel. Same transcribe(bytes) -> str interface.

    FunASR wraps audio loading, tagging, and text-normalization in one call;
    the return shape is a list of dicts with a 'text' field that contains
    embedded tags like <|en|><|NEUTRAL|><|Speech|> which we strip before return.
    """

    # SenseVoice-Small runs comfortably in real-time on CPU; streaming partials
    # work at our 1.5s tick rate.
    supports_streaming: bool = True

    # FunASR embeds language/emotion/event tags inline in the output text
    # using this pattern, e.g. "<|en|><|NEUTRAL|><|Speech|>Hello world".
    # Strip all such tags so downstream code only sees the transcript.
    _TAG_RE = re.compile(r"<\|[^|]+\|>")

    def __init__(self, model: str = "iic/SenseVoiceSmall"):
        self.model_name = model
        self._model = None
        self._load_lock = threading.Lock()

    def _load(self):
        with self._load_lock:
            if self._model is None:
                logger.info(f"Loading SenseVoice model '{self.model_name}'...")
                from funasr import AutoModel
                self._model = AutoModel(
                    model=self.model_name,
                    trust_remote_code=True,
                    disable_update=True,
                )
                logger.info("SenseVoice model loaded.")
            return self._model

    def warm(self):
        try:
            self._load()
        except Exception as e:
            logger.error(f"Failed to preload SenseVoice model: {e}")

    def transcribe(self, audio_bytes: bytes) -> str:
        if not audio_bytes:
            return ""
        try:
            audio = _decode_wav_to_float32(audio_bytes)
            if audio is None or audio.size == 0:
                return ""

            model = self._load()
            # Passing a numpy array (not a file path) bypasses FunASR's
            # ffmpeg-based audio loader — no ffmpeg binary required on PATH.
            # fs=16000 tells generate() our sample rate; data_type="sound"
            # disambiguates from text-mode inputs.
            results = model.generate(
                input=audio,
                fs=16000,
                data_type="sound",
                cache={},
                language="auto",
                use_itn=True,   # inverse text normalization: "7 point 5" → "7.5"
                batch_size_s=60,
            )
            if not results:
                return ""
            raw = results[0].get("text", "") if isinstance(results[0], dict) else str(results[0])
            # Strip the embedded <|lang|><|emotion|><|event|> tags.
            return self._TAG_RE.sub("", raw).strip()
        except Exception as e:
            logger.error(f"SenseVoice transcription failed: {e}")
            return ""


def _decode_wav_to_float32(audio_bytes: bytes):
    """Pull int16 mono 16kHz PCM out of our recorder's WAV bytes → float32 array.

    Returns None on format mismatch so transcribe() can short-circuit.
    """
    with wave.open(io.BytesIO(audio_bytes)) as wf:
        if (
            wf.getsampwidth() != 2
            or wf.getnchannels() != 1
            or wf.getframerate() != 16000
        ):
            logger.error(
                f"SenseVoice expects mono 16-bit 16kHz WAV; got "
                f"{wf.getnchannels()}ch {wf.getsampwidth() * 8}-bit "
                f"{wf.getframerate()}Hz"
            )
            return None
        frames = wf.readframes(wf.getnframes())
    if not frames:
        return np.zeros(0, dtype=np.float32)
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
