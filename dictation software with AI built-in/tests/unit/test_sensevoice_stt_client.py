"""SenseVoice client tests — funasr is lazy-imported so these run without [sensevoice]."""
import io
import wave
import numpy as np
from unittest.mock import MagicMock, patch

from src.ai.sensevoice_stt_client import SenseVoiceSTTClient


def _wav(samples: np.ndarray, sr: int = 16000) -> bytes:
    pcm = np.clip(samples * 32767, -32768, 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def test_empty_audio_returns_empty_string():
    assert SenseVoiceSTTClient().transcribe(b"") == ""


def test_supports_streaming_is_true():
    assert SenseVoiceSTTClient.supports_streaming is True


def test_default_model_name():
    assert SenseVoiceSTTClient().model_name == "iic/SenseVoiceSmall"


def test_wrong_sample_rate_rejected():
    bad = _wav(np.zeros(100, dtype=np.float32), sr=44100)
    assert SenseVoiceSTTClient().transcribe(bad) == ""


def test_transcribe_strips_embedded_tags():
    """FunASR emits <|lang|><|emotion|><|event|> tags inline; we strip them."""
    client = SenseVoiceSTTClient()
    client._model = MagicMock()
    client._model.generate.return_value = [
        {"text": "<|en|><|NEUTRAL|><|Speech|>Hello world"}
    ]
    result = client.transcribe(_wav(np.array([0.1, 0.2], dtype=np.float32)))
    assert result == "Hello world"


def test_transcribe_handles_untagged_output():
    """Some generate calls return plain strings with no tags — pass through."""
    client = SenseVoiceSTTClient()
    client._model = MagicMock()
    client._model.generate.return_value = [{"text": "plain text"}]
    result = client.transcribe(_wav(np.array([0.1], dtype=np.float32)))
    assert result == "plain text"


def test_transcribe_handles_list_of_strings():
    """Older FunASR versions return a list of strings directly."""
    client = SenseVoiceSTTClient()
    client._model = MagicMock()
    client._model.generate.return_value = ["just a string"]
    result = client.transcribe(_wav(np.array([0.1], dtype=np.float32)))
    assert result == "just a string"


def test_transcribe_swallows_exceptions():
    client = SenseVoiceSTTClient()
    client._model = MagicMock()
    client._model.generate.side_effect = RuntimeError("model fell over")
    result = client.transcribe(_wav(np.array([0.1], dtype=np.float32)))
    assert result == ""


def test_warm_swallows_errors():
    client = SenseVoiceSTTClient()
    with patch.object(client, "_load", side_effect=ImportError("no funasr")):
        client.warm()
