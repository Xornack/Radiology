import pytest
from unittest.mock import MagicMock, patch
from src.core.orchestrator import DictationOrchestrator


def test_full_dictation_pipeline_logic():
    """
    Ensures the orchestrator correctly coordinates
    Recorder -> AI (via get_wav_bytes) -> Scrubber -> Wedge.
    """
    mock_recorder = MagicMock()
    mock_recorder.get_wav_bytes.return_value = b"fake-wav-audio"

    mock_whisper = MagicMock()
    mock_whisper.transcribe.return_value = "Patient John Doe period"

    mock_wedge = MagicMock()

    with patch('src.core.orchestrator.scrub_text',
               side_effect=lambda x: x.replace("John Doe", "[NAME]")):

        orch = DictationOrchestrator(
            recorder=mock_recorder,
            whisper_client=mock_whisper,
            wedge=mock_wedge
        )

        orch.handle_trigger_down()
        assert mock_recorder.start.called

        orch.handle_trigger_up(mode="wedge")
        assert mock_recorder.stop.called
        assert mock_whisper.transcribe.called

        # Whisper must receive WAV bytes, not a numpy array
        call_args = mock_whisper.transcribe.call_args[0][0]
        assert isinstance(call_args, bytes)

        # Scrubbed text must reach the wedge
        mock_wedge.type_text.assert_called_with("Patient [NAME].")


def test_orchestrator_generate_impression():
    """Orchestrator must delegate impression generation to the LLM client."""
    mock_llm = MagicMock()
    mock_llm.generate_impression.return_value = "Normal chest X-ray."

    orch = DictationOrchestrator(
        recorder=MagicMock(),
        whisper_client=MagicMock(),
        wedge=MagicMock(),
        llm_client=mock_llm
    )

    result = orch.generate_impression("Lungs are clear bilaterally.")

    mock_llm.generate_impression.assert_called_once_with("Lungs are clear bilaterally.")
    assert result == "Normal chest X-ray."


def test_orchestrator_generate_impression_no_llm_client():
    """If no LLM client is configured, generate_impression must return empty string."""
    orch = DictationOrchestrator(
        recorder=MagicMock(),
        whisper_client=MagicMock(),
        wedge=MagicMock()
    )
    result = orch.generate_impression("Some findings.")
    assert result == ""
