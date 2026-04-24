import os
from pathlib import Path

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


def _load_dotenv(env_path: Path) -> None:
    """Read KEY=VALUE lines from a .env file into os.environ (as a fallback).

    Existing environment variables always win, so a shell override is still
    authoritative. Used so secrets like `HF_TOKEN` can live in a gitignored
    file instead of being typed on every launch. Format: one `KEY=VALUE`
    per line, `#` for comments, optional matched surrounding quotes.
    """
    if not env_path.is_file():
        return
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Strip matching surrounding quotes so HF_TOKEN="hf_xxx" works.
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            os.environ.setdefault(key, value)
    except Exception as e:
        logger.warning(f"Failed to read .env at {env_path}: {e}")


# Project root = two levels up from this file (src/utils/settings.py).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# Load .env before Settings() reads os.getenv so the file's values take
# effect on first app start — no extra wiring in main.py needed.
_load_dotenv(_PROJECT_ROOT / ".env")


class Settings:
    """
    Application settings loaded from environment variables with safe defaults.
    Instantiate a fresh Settings() to pick up the current environment.
    """
    def __init__(self):
        # STT backend selector. One of:
        #   "whisper-local-cpu" (default), "whisper-local-gpu", "sensevoice".
        # Unknown values fall back to whisper-local-cpu so a typo in the env
        # doesn't silently disable dictation.
        self.stt_backend: str = os.getenv("STT_BACKEND", "whisper-local-cpu").lower()
        # Radiology-vocabulary correction on by default (user is a radiologist).
        # Set RADIOLOGY_MODE=0 / false / off to flip the default to off.
        rad_raw = os.getenv("RADIOLOGY_MODE", "1").strip().lower()
        self.radiology_mode: bool = rad_raw not in ("0", "false", "off", "no")
        self.whisper_model: str = os.getenv("WHISPER_MODEL", "base.en")
        self.llm_url: str = os.getenv(
            "LLM_URL", "http://localhost:8001/v1/completions"
        )
        self.ollama_url: str = os.getenv(
            "OLLAMA_URL", "http://localhost:11434/api/chat"
        )
        self.ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
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
