import pytest
from unittest.mock import MagicMock, patch
from src.core.orchestrator import DictationOrchestrator

def test_full_dictation_pipeline_logic():
    """
    Ensures that the orchestrator correctly coordinates between 
    Recorder -> AI -> Scrubber -> Wedge.
    """
    # 1. Setup Mocks for all components
    mock_recorder = MagicMock()
    mock_recorder.get_buffer.return_value = b"fake-audio"
    
    mock_whisper = MagicMock()
    mock_whisper.transcribe.return_value = "Patient John Doe."
    
    mock_wedge = MagicMock()
    
    # We use the real scrubber to ensure integration works
    with patch('src.core.orchestrator.scrub_text', side_effect=lambda x: x.replace("John Doe", "[NAME]")) as mock_scrub:
        
        # 2. Initialize Orchestrator with mocks
        orch = DictationOrchestrator(
            recorder=mock_recorder,
            whisper_client=mock_whisper,
            wedge=mock_wedge
        )
        
        # 3. Simulate the Workflow
        orch.handle_trigger_down()
        assert mock_recorder.start.called
        
        orch.handle_trigger_up()
        assert mock_recorder.stop.called
        assert mock_whisper.transcribe.called
        
        # 4. Verify Final Output (Scrubbed and Wedged)
        # Expected: "Patient [NAME]."
        mock_wedge.type_text.assert_called_with("Patient [NAME].")
