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
        self.speechmike_vid: int = _safe_int(
            os.getenv("SPEECHMIKE_VID", "0x0911"), 0x0911, "SPEECHMIKE_VID"
        )
        self.speechmike_pid: int = _safe_int(
            os.getenv("SPEECHMIKE_PID", "0x0c1c"), 0x0c1c, "SPEECHMIKE_PID"
        )


# Module-level singleton — override by constructing Settings() directly in tests
settings = Settings()
