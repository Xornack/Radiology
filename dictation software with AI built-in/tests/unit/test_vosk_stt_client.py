"""Vosk client tests — vosk is lazy-imported so these run without [vosk]."""
import io
import json
import wave
import numpy as np
from unittest.mock import MagicMock, patch

from src.ai.vosk_stt_client import VoskSTTClient


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
    assert VoskSTTClient(model_path="/fake").transcribe(b"") == ""


def test_supports_streaming_is_true():
    """Vosk is built for streaming; partials tick through fine."""
    assert VoskSTTClient.supports_streaming is True


def test_wrong_sample_rate_rejected():
    bad = _wav(np.zeros(100, dtype=np.float32), sr=44100)
    assert VoskSTTClient(model_path="/fake").transcribe(bad) == ""


def test_transcribe_reads_final_result_text():
    """Happy path: KaldiRecognizer.FinalResult() JSON's text field is returned."""
    client = VoskSTTClient(model_path="/fake")
    client._model = object()  # bypass _load()
    fake_rec = MagicMock()
    fake_rec.FinalResult.return_value = json.dumps({"text": "hello there"})
    fake_vosk = MagicMock()
    fake_vosk.KaldiRecognizer.return_value = fake_rec
    with patch.dict("sys.modules", {"vosk": fake_vosk}):
        result = client.transcribe(_wav(np.array([0.1, 0.2], dtype=np.float32)))
    assert result == "hello there"


def test_transcribe_handles_empty_text_field():
    """Silent audio → empty text field → empty string (not a crash)."""
    client = VoskSTTClient(model_path="/fake")
    client._model = object()
    fake_rec = MagicMock()
    fake_rec.FinalResult.return_value = json.dumps({"text": ""})
    fake_vosk = MagicMock()
    fake_vosk.KaldiRecognizer.return_value = fake_rec
    with patch.dict("sys.modules", {"vosk": fake_vosk}):
        result = client.transcribe(_wav(np.array([0.1], dtype=np.float32)))
    assert result == ""


def test_transcribe_swallows_exceptions():
    client = VoskSTTClient(model_path="/fake")
    client._model = object()
    fake_vosk = MagicMock()
    fake_vosk.KaldiRecognizer.side_effect = RuntimeError("bad model")
    with patch.dict("sys.modules", {"vosk": fake_vosk}):
        result = client.transcribe(_wav(np.array([0.1], dtype=np.float32)))
    assert result == ""


def test_warm_swallows_errors():
    client = VoskSTTClient(model_path="/fake")
    with patch.object(client, "_load", side_effect=FileNotFoundError("no model")):
        client.warm()
