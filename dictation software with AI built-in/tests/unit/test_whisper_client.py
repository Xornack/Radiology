import pytest
from unittest.mock import patch, MagicMock
from src.ai.whisper_client import WhisperClient

def test_transcribe_audio_success():
    """
    Ensures that WhisperClient correctly sends audio bytes and returns
    the transcribed text from a successful API response.
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"text": "Hello, this is a test transcription."}
    
    with patch('requests.post', return_value=mock_response):
        client = WhisperClient(url="http://localhost:8000/transcribe")
        audio_data = b"fake-audio-bytes"
        result = client.transcribe(audio_data)
        
        assert result == "Hello, this is a test transcription."

def test_transcribe_audio_error_handling():
    """
    Ensures that WhisperClient handles API errors gracefully (e.g., returns empty string).
    """
    mock_response = MagicMock()
    mock_response.status_code = 500
    
    with patch('requests.post', return_value=mock_response):
        client = WhisperClient(
            url="http://localhost:8000/transcribe", retry_initial_delay=0
        )
        result = client.transcribe(b"bad-data")
        assert result == ""
