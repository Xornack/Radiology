"""On-device STT using Google Health AI's MedASR model.

Conformer-based ASR (~105M params) specifically trained on physician
dictation — Google reports 4.6% WER on radiology dictation vs. ~25% for
Whisper v3 Large on the same benchmark. English only.

Requires the optional `[medasr]` extra:
    pip install -e '.[medasr]'

Also requires Hugging Face auth plus Health AI Developer Foundations
license acceptance (one-time):
    huggingface-cli login
    # then visit https://huggingface.co/google/medasr and click Accept.
"""
import re

from loguru import logger

from src.ai._common import BaseSTTClient, decode_wav_to_float32


# MedASR emits punctuation as inline `{word}` tags — confirmed against
# google/medasr's own test_audio.wav for `{period}`, `{comma}`, `{colon}`,
# `{new paragraph}`, and reported by users for `{question mark}`. Rather
# than enumerate the full list (MedASR could add more at any time), strip
# the braces generically and let the shared `_substitute_tokens` pass in
# `punctuation.py` convert the spoken word to the real glyph — that
# function already handles every token the Whisper path handles.
_MEDASR_TAG_RE = re.compile(r"\{([A-Za-z][A-Za-z \-]*)\}")


def _expand_medasr_tags(text: str) -> str:
    """Strip the curly braces from MedASR's `{period}` / `{question mark}` /
    `{new paragraph}` etc. so the downstream punctuation pipeline can
    substitute the inner word for its glyph. Pads with spaces to keep the
    content a standalone word run even when the model emits the tag flush
    against its neighbors (e.g. `fast{new paragraph}findings`)."""
    text = _MEDASR_TAG_RE.sub(lambda m: " " + m.group(1) + " ", text)
    # Collapse runs of spaces left behind so the downstream pipeline sees
    # a tidy sequence of words.
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


class MedASRSTTClient(BaseSTTClient):
    """STT via Google's MedASR. Feeds a numpy float32 array straight to the
    processor — our recorder's WAV bytes already match MedASR's expected
    mono 16-bit 16 kHz format, so no intermediate file / librosa needed.
    """

    name = "MedASR"
    # 105M params; fast enough on GPU for live partials. CPU works but is
    # slower per tick — users who need pure CPU should prefer
    # whisper-local-cpu.
    supports_streaming = True
    # MedASR emits `{period}` / `{comma}` / `{colon}` / `{new paragraph}`
    # which `_expand_medasr_tags` rewrites to real glyphs. Signal to the
    # text pipeline that its Whisper-style punctuation stripper must NOT
    # run on our output — otherwise it erases the periods we just added.
    emits_punctuation = True

    def __init__(self, model_id: str = "google/medasr"):
        super().__init__()
        self.model_id = model_id
        # Processor + model are loaded as a pair. Dual-attribute pattern
        # matches GemmaSTTClient so tests can pre-wire either independently.
        self._processor = None

    def _load_locked(self):
        # Base class caches only a single self._model; MedASR needs two.
        if self._model is None or self._processor is None:
            self._processor, self._model = self._load_impl()
        return (self._processor, self._model)

    def _load_impl(self):
        logger.info(f"Loading MedASR model '{self.model_id}'...")
        try:
            # Direct submodule imports avoid the transformers `_LazyModule`
            # attribute race that bites when another thread is concurrently
            # importing transformers (see stt_registry._build_medasr).
            from transformers.models.auto.modeling_auto import AutoModelForCTC
            from transformers.models.auto.processing_auto import AutoProcessor
        except ImportError as e:
            raise ImportError(
                "MedASR requires the [medasr] extra "
                f"(missing: {getattr(e, 'name', None) or e}). "
                "Install with: pip install -e '.[medasr]'"
            ) from e
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        processor = AutoProcessor.from_pretrained(self.model_id)
        model = AutoModelForCTC.from_pretrained(self.model_id).to(device)
        logger.info(f"MedASR model loaded on {device}.")
        return (processor, model)

    def _transcribe(self, audio_bytes: bytes) -> str:
        audio = decode_wav_to_float32(audio_bytes, backend_name=self.name)
        if audio is None or audio.size == 0:
            return ""
        processor, model = self._load()
        inputs = processor(
            audio,
            sampling_rate=16000,
            return_tensors="pt",
            padding=True,
        )
        inputs = inputs.to(model.device)
        # Per the MedASR HF model card: this variant ships a decoder head
        # that transformers exposes through the standard generate() API
        # rather than the more typical CTC-argmax path.
        import torch
        with torch.no_grad():
            outputs = model.generate(**inputs)
        # `skip_special_tokens=True` drops `</s>` (emitted at every pause);
        # the remaining `{period}`-style inline tags are rewritten next.
        decoded = processor.batch_decode(outputs, skip_special_tokens=True)
        if not decoded:
            return ""
        return _expand_medasr_tags(decoded[0])
