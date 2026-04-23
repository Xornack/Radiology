import os
from loguru import logger


def _safe_int(val: str, default: int, name: str) -> int:
    """Parse hex (0x0911) or decimal ints. Fall back to default on malformed input."""
    try:
        return int(val, 0)
    except (ValueError, TypeError):
        logger.warning(
            f"Invalid {name}={val!r}; falling back to default 0x{default:04x}"
        )
        return default


class Settings:
    """
    Application settings loaded from environment variables with safe defaults.
    Instantiate a fresh Settings() to pick up the current environment.
    """
    def __init__(self):
        # STT backend selector. One of:
        #   "whisper-local-cpu" (default), "whisper-local-gpu", "whisper-http",
        #   "gemma-e2b", "gemma-e2b-4bit", "gemma-e4b", "gemma-e4b-4bit",
        #   "moonshine-tiny", "moonshine-base", "parakeet-tdt", "vosk".
        # "whisper-local" is accepted as a legacy alias for whisper-local-cpu.
        # Unknown values fall back to whisper-local-cpu so a typo in the env
        # doesn't silently disable dictation.
        self.stt_backend: str = os.getenv("STT_BACKEND", "whisper-local-cpu").lower()
        # Parakeet-TDT model ID (NeMo HF Hub repo). Defaults to the 0.6B v2
        # which is the best accuracy/latency tradeoff for radiology speech.
        self.parakeet_model: str = os.getenv(
            "PARAKEET_MODEL", "nvidia/parakeet-tdt-0.6b-v2"
        )
        # Vosk requires a manually-downloaded model directory — no HF/hub
        # fetch. Leave empty until the user sets the path; the builder will
        # raise a clear error on first selection rather than crashing later.
        self.vosk_model_path: str = os.getenv("VOSK_MODEL_PATH", "")
        # Radiology-vocabulary correction on by default (user is a radiologist).
        # Set RADIOLOGY_MODE=0 / false / off to flip the default to off.
        rad_raw = os.getenv("RADIOLOGY_MODE", "1").strip().lower()
        self.radiology_mode: bool = rad_raw not in ("0", "false", "off", "no")
        # "local" runs faster-whisper in-process (no server needed).
        # "http" uses WhisperClient against WHISPER_URL.
        self.whisper_mode: str = os.getenv("WHISPER_MODE", "local").lower()
        self.whisper_url: str = os.getenv(
            "WHISPER_URL", "http://localhost:8000/transcribe"
        )
        self.whisper_model: str = os.getenv("WHISPER_MODEL", "base.en")
        # CPU+int8 works everywhere without CUDA Toolkit. To use GPU, install
        # CUDA Toolkit 12.x (or `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12`)
        # and set WHISPER_DEVICE=cuda, WHISPER_COMPUTE_TYPE=float16.
        self.whisper_device: str = os.getenv("WHISPER_DEVICE", "cpu")
        self.whisper_compute_type: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
        self.llm_url: str = os.getenv(
            "LLM_URL", "http://localhost:8001/v1/completions"
        )
        # Default targets Nuance PowerMic II-NS (VID 0x0554 / PID 0x1001).
        # For other mics, override via SPEECHMIKE_VID / SPEECHMIKE_PID env vars.
        # Use `python tools/hid_probe.py list` to find the IDs for your device.
        # Known alternates: Philips SpeechMike → 0x0911 / 0x0c1c.
        self.speechmike_vid: int = _safe_int(
            os.getenv("SPEECHMIKE_VID", "0x0554"), 0x0554, "SPEECHMIKE_VID"
        )
        self.speechmike_pid: int = _safe_int(
            os.getenv("SPEECHMIKE_PID", "0x1001"), 0x1001, "SPEECHMIKE_PID"
        )


# Module-level singleton — override by constructing Settings() directly in tests
settings = Settings()
