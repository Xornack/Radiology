import io
import wave
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from src.hardware.recorder import AudioRecorder


def test_recorder_initialization():
    """Ensures the recorder is initialized with the correct Whisper settings (16kHz, Mono)."""
    recorder = AudioRecorder(sample_rate=16000)
    assert recorder.sample_rate == 16000
    assert recorder.channels == 1


def test_recorder_captures_data():
    """Mocks a sounddevice InputStream and ensures the callback appends data to the buffer."""
    recorder = AudioRecorder()
    fake_audio = np.array([[0.1], [0.2], [0.3]], dtype='float32')
    recorder._audio_callback(fake_audio, 3, None, None)

    assert len(recorder.get_buffer()) > 0
    assert recorder.get_buffer()[0] == pytest.approx(0.1)


def test_recorder_start_stop():
    """Ensures start and stop methods call the underlying sounddevice stream."""
    with patch('sounddevice.InputStream') as mock_stream:
        recorder = AudioRecorder()
        recorder.start()
        assert mock_stream.return_value.start.called

        recorder.stop()
        assert mock_stream.return_value.stop.called


def test_recorder_get_wav_bytes_is_valid_wav():
    """get_wav_bytes() must return parseable 16-bit mono 16kHz WAV bytes."""
    recorder = AudioRecorder(sample_rate=16000, channels=1)
    fake_audio = np.array([[0.1], [0.2], [-0.1], [0.0]], dtype='float32')
    recorder._audio_callback(fake_audio, 4, None, None)

    wav_bytes = recorder.get_wav_bytes()

    assert isinstance(wav_bytes, bytes)
    assert len(wav_bytes) > 0

    with wave.open(io.BytesIO(wav_bytes)) as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2   # 16-bit PCM
        assert wf.getframerate() == 16000


def test_recorder_get_wav_bytes_empty_buffer():
    """get_wav_bytes() on an empty buffer must still return a valid (silent) WAV."""
    recorder = AudioRecorder()
    wav_bytes = recorder.get_wav_bytes()
    assert isinstance(wav_bytes, bytes)
    with wave.open(io.BytesIO(wav_bytes)) as wf:
        assert wf.getnframes() == 0


def test_recorder_logs_audio_status_errors():
    """A truthy status from the audio callback must not silently discard data."""
    recorder = AudioRecorder()
    fake_audio = np.array([[0.5]] * 10, dtype='float32')
    # Pass a truthy status string — callback must still capture audio
    recorder._audio_callback(fake_audio, 10, None, "input overflow")
    assert len(recorder.get_buffer()) == 10


def test_recorder_start_closes_existing_stream():
    """Calling start() twice must stop/close the first stream before opening a new one."""
    with patch('sounddevice.InputStream') as mock_stream_cls:
        recorder = AudioRecorder()
        recorder.start()
        first_stream = mock_stream_cls.return_value

        recorder.start()   # Second start must close the first stream
        first_stream.stop.assert_called_once()
        first_stream.close.assert_called_once()


def test_recorder_start_raises_on_device_failure():
    """If the audio device is unavailable, start() must propagate the error."""
    with patch('sounddevice.InputStream', side_effect=OSError("No audio device")):
        recorder = AudioRecorder()
        with pytest.raises(OSError):
            recorder.start()
