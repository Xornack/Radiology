import os
import pytest
from src.utils.settings import Settings


def test_settings_default_values():
    """Settings must provide safe defaults when no environment variables are set."""
    s = Settings()
    assert s.whisper_model == "base.en"
    assert s.llm_url == "http://localhost:8001/v1/completions"
    assert isinstance(s.speechmike_vid, int)
    assert isinstance(s.speechmike_pid, int)
    assert s.speechmike_vid == 0x0554   # Nuance PowerMic II-NS
    assert s.speechmike_pid == 0x1001


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


def test_settings_default_stt_backend_is_whisper_local_cpu():
    """STT defaults to local Whisper on CPU — zero-setup on any machine."""
    s = Settings()
    assert s.stt_backend == "whisper-local-cpu"


def test_settings_stt_backend_env_override(monkeypatch):
    """STT_BACKEND env var selects a different backend (case-insensitive)."""
    monkeypatch.setenv("STT_BACKEND", "SenseVoice")
    s = Settings()
    assert s.stt_backend == "sensevoice"


def test_settings_whisper_model_env_override(monkeypatch):
    """WHISPER_MODEL selects the faster-whisper model size."""
    monkeypatch.setenv("WHISPER_MODEL", "small.en")
    s = Settings()
    assert s.whisper_model == "small.en"


def test_settings_radiology_mode_defaults_on():
    """Default: user is a radiologist, vocabulary correction starts on."""
    s = Settings()
    assert s.radiology_mode is True


def test_settings_radiology_mode_disabled_by_env(monkeypatch):
    """RADIOLOGY_MODE=0 flips the startup default off for non-radiology users."""
    for off_value in ("0", "false", "False", "off", "no"):
        monkeypatch.setenv("RADIOLOGY_MODE", off_value)
        s = Settings()
        assert s.radiology_mode is False, f"{off_value!r} should disable"


# --- .env loader ---

def test_dotenv_loader_sets_missing_env_vars(tmp_path, monkeypatch):
    """KEY=VALUE lines should populate os.environ for variables not already set."""
    from src.utils.settings import _load_dotenv
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# a comment\n"
        "\n"
        "FOO_TEST_SETTING=bar\n"
        'BAZ_TEST_SETTING="hello world"\n'
        "QUX_TEST_SETTING='single quoted'\n"
    )
    for key in ("FOO_TEST_SETTING", "BAZ_TEST_SETTING", "QUX_TEST_SETTING"):
        monkeypatch.delenv(key, raising=False)
    _load_dotenv(env_file)
    assert os.environ["FOO_TEST_SETTING"] == "bar"
    assert os.environ["BAZ_TEST_SETTING"] == "hello world"
    assert os.environ["QUX_TEST_SETTING"] == "single quoted"


def test_dotenv_loader_does_not_overwrite_existing_env(tmp_path, monkeypatch):
    """A value set in the shell must win over the .env fallback."""
    import os
    from src.utils.settings import _load_dotenv
    env_file = tmp_path / ".env"
    env_file.write_text("FOO_TEST_OVERRIDE=from_file\n")
    monkeypatch.setenv("FOO_TEST_OVERRIDE", "from_shell")
    _load_dotenv(env_file)
    assert os.environ["FOO_TEST_OVERRIDE"] == "from_shell"


def test_dotenv_loader_ignores_missing_file(tmp_path):
    """No .env? Loader is a silent no-op — never raises."""
    from src.utils.settings import _load_dotenv
    _load_dotenv(tmp_path / "does_not_exist.env")


def test_dotenv_loader_skips_malformed_lines(tmp_path, monkeypatch):
    """Lines without '=' are silently skipped rather than blowing up."""
    import os
    from src.utils.settings import _load_dotenv
    env_file = tmp_path / ".env"
    env_file.write_text("just_a_word_no_equals\nVALID_TEST_KEY=ok\n")
    monkeypatch.delenv("VALID_TEST_KEY", raising=False)
    _load_dotenv(env_file)
    assert os.environ["VALID_TEST_KEY"] == "ok"
