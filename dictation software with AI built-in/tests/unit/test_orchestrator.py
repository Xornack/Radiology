from unittest.mock import MagicMock, patch
from src.core.orchestrator import DictationOrchestrator


def _make_orch(transcription: str = "hello world"):
    mock_recorder = MagicMock()
    mock_recorder.get_wav_bytes.return_value = b"wav"
    mock_whisper = MagicMock()
    mock_whisper.transcribe.return_value = transcription
    mock_wedge = MagicMock()
    return DictationOrchestrator(
        recorder=mock_recorder,
        whisper_client=mock_whisper,
        wedge=mock_wedge,
    )


def test_handle_trigger_up_inapp_mode_does_not_call_wedge():
    """In-app mode routes text only to the caller, never to the wedge."""
    orch = _make_orch("Findings comma normal period")
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        result = orch.handle_trigger_up(mode="inapp")
    assert result == "Findings, normal."
    orch.wedge.type_text.assert_not_called()


def test_handle_trigger_up_wedge_mode_calls_wedge_and_returns_text():
    """Wedge mode sends text via SendInput AND returns it for history display."""
    orch = _make_orch("Chest clear period")
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        result = orch.handle_trigger_up(mode="wedge")
    assert result == "Chest clear."
    orch.wedge.type_text.assert_called_once_with("Chest clear.")


def test_handle_trigger_up_wedge_mode_empty_text_skips_wedge():
    """Empty transcriptions must not be injected externally."""
    orch = _make_orch("")
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        result = orch.handle_trigger_up(mode="wedge")
    assert result == ""
    orch.wedge.type_text.assert_not_called()


def test_handle_trigger_up_defaults_to_inapp_mode():
    """Default mode must be 'inapp' so new callers don't accidentally emit keystrokes."""
    orch = _make_orch("hello")
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        orch.handle_trigger_up()
    orch.wedge.type_text.assert_not_called()
