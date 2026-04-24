"""On-device STT using Alibaba's SenseVoice via the FunASR framework.

Small multilingual ASR (~100M params) with built-in language detection,
emotion classification, and audio-event tagging. Fast on CPU, very fast
on GPU. The tagging features are interesting for future clinical cues
(e.g. detecting "stressed" speech during emergent dictations) but for now
we only consume the plain transcription text.

Requires the optional `[sensevoice]` extra:
    pip install -e '.[sensevoice]'
"""
import re

from loguru import logger

from src.ai._common import BaseSTTClient, decode_wav_to_float32


class SenseVoiceSTTClient(BaseSTTClient):
    """STT via `funasr` AutoModel. Same transcribe(bytes) -> str interface.

    FunASR wraps audio loading, tagging, and text-normalization in one call;
    the return shape is a list of dicts with a 'text' field that contains
    embedded tags like <|en|><|NEUTRAL|><|Speech|> which we strip before return.
    """

    name = "SenseVoice"
    # SenseVoice-Small runs comfortably in real-time on CPU; streaming partials
    # work at our 1.5s tick rate.
    supports_streaming = True

    # FunASR embeds language/emotion/event tags inline in the output text
    # using this pattern, e.g. "<|en|><|NEUTRAL|><|Speech|>Hello world".
    # Strip all such tags so downstream code only sees the transcript.
    _TAG_RE = re.compile(r"<\|[^|]+\|>")

    def __init__(self, model: str = "iic/SenseVoiceSmall"):
        super().__init__()
        self.model_name = model

    def _load_impl(self):
        logger.info(f"Loading SenseVoice model '{self.model_name}'...")
        # FunASR + its pydub dep are noisy about missing ffmpeg even though
        # we feed it numpy arrays directly (never hitting the ffmpeg path).
        # Gag both the RuntimeWarning from pydub and the "Notice: ffmpeg..."
        # stdout print from FunASR so the app log stays clean. Users who
        # install ffmpeg system-wide won't see them either way.
        import contextlib
        import io as _io
        import warnings
        with warnings.catch_warnings(), contextlib.redirect_stdout(_io.StringIO()):
            warnings.filterwarnings(
                "ignore",
                message=r"Couldn't find ffmpeg",
                category=RuntimeWarning,
            )
            from funasr import AutoModel
            model = AutoModel(
                model=self.model_name,
                trust_remote_code=True,
                disable_update=True,
            )
        logger.info("SenseVoice model loaded.")
        return model

    def _transcribe(self, audio_bytes: bytes) -> str:
        audio = decode_wav_to_float32(audio_bytes, backend_name=self.name)
        if audio is None or audio.size == 0:
            return ""

        model = self._load()
        # Passing a numpy array (not a file path) bypasses FunASR's
        # ffmpeg-based audio loader — no ffmpeg binary required on PATH.
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
        first = results[0]
        raw = first.get("text", "") if isinstance(first, dict) else str(first)
        return self._TAG_RE.sub("", raw).strip()
