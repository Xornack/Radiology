import pytest
from src.utils.settings import Settings


def test_settings_default_values():
    """Settings must provide safe defaults when no environment variables are set."""
    s = Settings()
    assert s.whisper_url == "http://localhost:8000/transcribe"
    assert s.llm_url == "http://localhost:8001/v1/completions"
    assert isinstance(s.speechmike_vid, int)
    assert isinstance(s.speechmike_pid, int)
    assert s.speechmike_vid == 0x0554   # Nuance PowerMic II-NS
    assert s.speechmike_pid == 0x1001


def test_settings_reads_whisper_url_from_env(monkeypatch):
    """WHISPER_URL environment variable must override the default."""
    monkeypatch.setenv("WHISPER_URL", "http://gpu-server:9000/transcribe")
    s = Settings()
    assert s.whisper_url == "http://gpu-server:9000/transcribe"


def test_settings_reads_llm_url_from_env(monkeypatch):
    """LLM_URL environment variable must override the default."""
    monkeypatch.setenv("LLM_URL", "http://gpu-server:9001/v1/completions")
    s = Settings()
    assert s.llm_url == "http://gpu-server:9001/v1/completions"


def test_settings_reads_hid_ids_from_env(monkeypatch):
    """SPEECHMIKE_VID/PID env vars must be parsed correctly (hex and decimal)."""
    monkeypatch.setenv("SPEECHMIKE_VID", "0x0912")
    monkeypatch.setenv("SPEECHMIKE_PID", "0x0c1d")
    s = Settings()
    assert s.speechmike_vid == 0x0912
    assert s.speechmike_pid == 0x0c1d


def test_settings_reads_decimal_hid_ids(monkeypatch):
    """HID IDs specified as plain decimals must also parse correctly."""
    monkeypatch.setenv("SPEECHMIKE_VID", "2322")
    monkeypatch.setenv("SPEECHMIKE_PID", "3100")
    s = Settings()
    assert s.speechmike_vid == 2322
    assert s.speechmike_pid == 3100
