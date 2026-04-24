"""On-device STT using `faster-whisper` in-process. No server required."""
from loguru import logger

from src.ai._common import BaseSTTClient, decode_wav_to_float32


class LocalWhisperClient(BaseSTTClient):
    """In-process STT using faster-whisper.

    The model loads lazily on first transcribe() call; call warm() to preload
    it in a background thread so the first dictation isn't delayed.
    """

    name = "Whisper"
    # Whisper is fast enough to drive 1.5s streaming ticks.
    supports_streaming = True

    def __init__(
        self,
        model_size: str = "base.en",
        device: str = "auto",
        compute_type: str = "auto",
    ):
        super().__init__()
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

    def _load_impl(self):
        logger.info(
            f"Loading faster-whisper model '{self.model_size}' "
            f"(device={self.device}, compute_type={self.compute_type})..."
        )
        # Deferred import: heavy dependency, only needed when local mode is used
        from faster_whisper import WhisperModel
        model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )
        logger.info("Whisper model loaded.")
        return model

    # Back-compat: some existing tests (and the Phase 1 patch) referenced
    # `_load_model`. Keep as a thin alias so the rename doesn't break them.
    def _load_model(self):
        return self._load()

    def _transcribe(self, audio_bytes: bytes) -> str:
        audio = decode_wav_to_float32(audio_bytes, backend_name=self.name)
        if audio is None or audio.size == 0:
            return ""
        model = self._load()
        try:
            return self._run_transcribe(model, audio)
        except Exception as e:
            # CUDA runtime errors (missing cuBLAS/cuDNN) only surface at
            # inference time — fall back to CPU and retry once.
            msg = str(e).lower()
            cuda_failed = (
                self.device == "cuda"
                and ("cuda" in msg or "cublas" in msg or "cudnn" in msg)
            )
            if not cuda_failed:
                raise
            logger.warning(
                f"CUDA inference failed ({e}); falling back to CPU+int8."
            )
            # Reset AND reload under a single lock so a concurrent transcribe()
            # can't see an intermediate state (device=cpu but old cuda _model
            # still live).
            with self._load_lock:
                self.device = "cpu"
                self.compute_type = "int8"
                self._model = None
                model = self._load_locked()
            return self._run_transcribe(model, audio)

    @staticmethod
    def _run_transcribe(model, audio) -> str:
        segments, _info = model.transcribe(
            audio,
            beam_size=1,
            language="en",
            vad_filter=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
