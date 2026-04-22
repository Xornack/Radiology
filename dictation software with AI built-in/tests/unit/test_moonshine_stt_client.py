"""Moonshine client tests — the moonshine package itself is lazy-imported
inside _load(), so these run on a base install without the [moonshine] extra."""
import io
import wave
import numpy as np
from unittest.mock import MagicMock, patch

from src.ai.moonshine_stt_client import MoonshineSTTClient, _decode_wav_to_float32


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
    assert MoonshineSTTClient().transcribe(b"") == ""


def test_supports_streaming_is_true():
    """Moonshine is fast enough for 1.5s live partials."""
    assert MoonshineSTTClient.supports_streaming is True


def test_default_model_is_base():
    assert MoonshineSTTClient().model_name == "moonshine/base"


def test_tiny_variant_selectable():
    assert MoonshineSTTClient(model="moonshine/tiny").model_name == "moonshine/tiny"


def test_wrong_sample_rate_rejected():
    bad = _wav(np.zeros(100, dtype=np.float32), sr=44100)
    assert MoonshineSTTClient().transcribe(bad) == ""


def test_transcribe_returns_joined_segments():
    """moonshine.transcribe returning a list of segments is collapsed to a string."""
    client = MoonshineSTTClient()
    client._model = object()  # bypass _load()
    fake_mod = MagicMock()
    fake_mod.transcribe.return_value = ["  hello  ", " world. "]
    with patch.dict("sys.modules", {"moonshine_onnx": fake_mod}):
        result = client.transcribe(_wav(np.array([0.1, 0.2], dtype=np.float32)))
    assert result == "hello world."


def test_transcribe_handles_string_return():
    """Some versions return the transcript directly as a string, not a list."""
    client = MoonshineSTTClient()
    client._model = object()
    fake_mod = MagicMock()
    fake_mod.transcribe.return_value = "  hello  "
    with patch.dict("sys.modules", {"moonshine_onnx": fake_mod}):
        result = client.transcribe(_wav(np.array([0.1], dtype=np.float32)))
    assert result == "hello"


def test_transcribe_swallows_exceptions():
    client = MoonshineSTTClient()
    client._model = object()
    fake_mod = MagicMock()
    fake_mod.transcribe.side_effect = RuntimeError("model barfed")
    with patch.dict("sys.modules", {"moonshine_onnx": fake_mod}):
        result = client.transcribe(_wav(np.array([0.1], dtype=np.float32)))
    assert result == ""


def test_warm_swallows_errors():
    client = MoonshineSTTClient()
    with patch.object(client, "_load", side_effect=ImportError("no moonshine")):
        client.warm()
