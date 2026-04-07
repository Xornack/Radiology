import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from src.hardware.recorder import AudioRecorder

def test_recorder_initialization():
    """
    Ensures the recorder is initialized with the correct Whisper settings
    (16kHz, Mono).
    """
    recorder = AudioRecorder(sample_rate=16000)
    assert recorder.sample_rate == 16000
    assert recorder.channels == 1

def test_recorder_captures_data():
    """
    Mocks a sounddevice InputStream and ensures that the callback
    correctly appends data to the internal buffer.
    """
    recorder = AudioRecorder()
    
    # Mock some incoming audio data (numpy array)
    fake_audio = np.array([[0.1], [0.2], [0.3]], dtype='float32')
    
    # Simulate the sounddevice callback
    # callback(indata, frames, time, status)
    recorder._audio_callback(fake_audio, 3, None, None)
    
    assert len(recorder.get_buffer()) > 0
    # Whisper expects 16-bit PCM or float32. We check if data is stored.
    assert recorder.get_buffer()[0] == 0.1

def test_recorder_start_stop():
    """
    Ensures start and stop methods call the underlying sounddevice stream.
    """
    with patch('sounddevice.InputStream') as mock_stream:
        recorder = AudioRecorder()
        recorder.start()
        assert mock_stream.return_value.start.called
        
        recorder.stop()
        assert mock_stream.return_value.stop.called
