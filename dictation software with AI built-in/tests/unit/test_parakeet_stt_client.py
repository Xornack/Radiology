"""Parakeet client tests. NeMo is lazy-imported so these run without [parakeet]."""
import io
import wave
import numpy as np
from unittest.mock import MagicMock, patch

from src.ai.parakeet_stt_client import ParakeetSTTClient


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
    assert ParakeetSTTClient().transcribe(b"") == ""


def test_supports_streaming_is_true():
    assert ParakeetSTTClient.supports_streaming is True


def test_default_model_name():
    assert ParakeetSTTClient().model_name == "nvidia/parakeet-tdt-0.6b-v2"


def test_custom_model_name_accepted():
    assert ParakeetSTTClient(model="nvidia/parakeet-tdt_ctc-110m").model_name == (
        "nvidia/parakeet-tdt_ctc-110m"
    )


def test_transcribe_returns_first_hypothesis_string():
    """NeMo returns a list; first element is the transcript for the single clip."""
    client = ParakeetSTTClient()
    client._model = MagicMock()
    client._model.transcribe.return_value = ["  hello world  "]
    result = client.transcribe(_wav(np.array([0.1, 0.2], dtype=np.float32)))
    assert result == "hello world"


def test_transcribe_handles_hypothesis_object_return():
    """Some NeMo versions return Hypothesis objects with a .text attr."""
    client = ParakeetSTTClient()
    client._model = MagicMock()
    hyp = MagicMock()
    hyp.text = "spoken text"
    client._model.transcribe.return_value = [hyp]
    result = client.transcribe(_wav(np.array([0.1], dtype=np.float32)))
    assert result == "spoken text"


def test_transcribe_swallows_exceptions():
    client = ParakeetSTTClient()
    client._model = MagicMock()
    client._model.transcribe.side_effect = RuntimeError("CUDA OOM")
    result = client.transcribe(_wav(np.array([0.1], dtype=np.float32)))
    assert result == ""


def test_warm_swallows_errors():
    client = ParakeetSTTClient()
    with patch.object(client, "_load", side_effect=ImportError("no nemo")):
        client.warm()
