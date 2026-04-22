"""On-device STT using Google's Gemma 4 multimodal LLMs.

Drop-in replacement for WhisperClient (same `transcribe(bytes) -> str` API).
Gemma 4 is a general LLM fed audio through its multimodal chat template —
much slower per second of audio than a dedicated ASR model like Whisper, so
streaming partials are disabled (see `supports_streaming`).

Requires the optional `[gemma]` extra: `pip install -e '.[gemma]'`.
"""
import io
import threading
import wave
import numpy as np
from loguru import logger


class GemmaSTTClient:
    """STT via `google/gemma-4-E2B` (default) or `google/gemma-4-E4B`.

    The model loads lazily on first transcribe() so startup stays fast; call
    warm() to preload in a background thread. HF auth is required the first
    time the weights are pulled (see README).
    """

    # Too slow per tick to drive live partials; UI skips streaming when this
    # client is active and shows the final transcript on Stop.
    supports_streaming: bool = False

    _TRANSCRIBE_PROMPT = (
        "Transcribe the following speech segment in its original language. "
        "Follow these specific instructions for formatting the answer:\n"
        "* Only output the transcription, with no newlines.\n"
        "* When transcribing numbers, write the digits, "
        "i.e. write 1.7 and not one point seven, and write 3 instead of three."
    )

    def __init__(self, model_id: str = "google/gemma-4-E2B-it", quantize_4bit: bool = False):
        self.model_id = model_id
        self.quantize_4bit = quantize_4bit
        self._model = None
        self._processor = None
        self._load_lock = threading.Lock()

    def _load(self):
        """Lazy-load processor + model. Holds a lock so concurrent callers share one load."""
        with self._load_lock:
            if self._model is None:
                label = f"{self.model_id}{' (4-bit)' if self.quantize_4bit else ''}"
                logger.info(f"Loading Gemma STT model '{label}'...")
                from transformers import AutoProcessor, AutoModelForMultimodalLM
                self._processor = AutoProcessor.from_pretrained(self.model_id)
                model_kwargs = dict(dtype="auto", device_map="auto")
                if self.quantize_4bit:
                    # nf4 + double-quant + bfloat16 compute: the standard
                    # QLoRA recipe for trimming ~75% off disk & VRAM with
                    # minimal accuracy loss. Requires bitsandbytes + CUDA.
                    import torch
                    from transformers import BitsAndBytesConfig
                    model_kwargs["quantization_config"] = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_compute_dtype=torch.bfloat16,
                    )
                self._model = AutoModelForMultimodalLM.from_pretrained(
                    self.model_id, **model_kwargs,
                )
                logger.info("Gemma STT model loaded.")
            return self._processor, self._model

    def warm(self):
        """Preload the model in a background thread. Safe to call multiple times."""
        try:
            self._load()
        except Exception as e:
            logger.error(f"Failed to preload Gemma STT model: {e}")

    def transcribe(self, audio_bytes: bytes) -> str:
        """Decode 16-bit mono 16kHz WAV bytes and run them through Gemma.

        Returns the transcript, or empty string on any failure so the
        dictation pipeline degrades gracefully.
        """
        if not audio_bytes:
            return ""
        try:
            audio = _decode_wav_to_float32(audio_bytes)
            if audio is None or audio.size == 0:
                return ""

            processor, model = self._load()
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": self._TRANSCRIBE_PROMPT},
                    {"type": "audio", "audio": audio},
                ],
            }]
            inputs = processor.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
            )
            inputs = inputs.to(model.device, dtype=model.dtype)

            input_len = inputs["input_ids"].shape[-1]
            outputs = model.generate(**inputs, max_new_tokens=512)
            # Slice off the prompt tokens so we only decode the model's reply.
            new_tokens = outputs[0][input_len:]
            text = processor.decode(new_tokens, skip_special_tokens=True)
            return text.strip()
        except Exception as e:
            logger.error(f"Gemma STT transcription failed: {e}")
            return ""


def _decode_wav_to_float32(audio_bytes: bytes):
    """Pull int16 mono 16kHz PCM from our recorder's WAV bytes → float32 array.

    Normalizes to [-1, 1] which is what the Gemma audio processor expects.
    Returns None on format mismatch.
    """
    with wave.open(io.BytesIO(audio_bytes)) as wf:
        if (
            wf.getsampwidth() != 2
            or wf.getnchannels() != 1
            or wf.getframerate() != 16000
        ):
            logger.error(
                f"Gemma STT expects mono 16-bit 16kHz WAV; got "
                f"{wf.getnchannels()}ch {wf.getsampwidth() * 8}-bit "
                f"{wf.getframerate()}Hz"
            )
            return None
        frames = wf.readframes(wf.getnframes())
    if not frames:
        return np.zeros(0, dtype=np.float32)
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
