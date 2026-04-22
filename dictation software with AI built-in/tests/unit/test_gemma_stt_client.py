"""Gemma STT client tests. Heavy deps (transformers, torch) are mocked via
sys.modules patching so the suite runs on a base install without [gemma] extras."""
import io
import sys
import wave
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from src.ai.gemma_stt_client import GemmaSTTClient, _decode_wav_to_float32


def _make_wav_bytes(samples: np.ndarray, sample_rate: int = 16000) -> bytes:
    """Build a 16-bit mono WAV blob from a float array in [-1, 1]."""
    pcm = np.clip(samples * 32767, -32768, 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def test_empty_audio_returns_empty_string():
    """No audio in, no transcription out — never raises."""
    client = GemmaSTTClient()
    assert client.transcribe(b"") == ""


def test_supports_streaming_is_false():
    """Gemma is too slow for 1.5s streaming ticks; UI must see that."""
    assert GemmaSTTClient.supports_streaming is False


def test_decode_wav_round_trip():
    """Helper correctly unpacks our recorder's WAV format into a float32 array."""
    samples = np.array([0.0, 0.5, -0.5, 0.1], dtype=np.float32)
    wav_bytes = _make_wav_bytes(samples)
    decoded = _decode_wav_to_float32(wav_bytes)
    assert decoded.dtype == np.float32
    assert decoded.shape == (4,)
    # int16 round-trip has at most 1/32768 loss per sample
    assert np.allclose(decoded, samples, atol=1e-4)


def test_decode_wav_rejects_wrong_sample_rate():
    """Non-16kHz input is reported as None so transcribe short-circuits."""
    wav_bytes = _make_wav_bytes(np.zeros(100, dtype=np.float32), sample_rate=44100)
    assert _decode_wav_to_float32(wav_bytes) is None


def test_decode_wav_empty_frames_returns_zero_length_array():
    """Zero-length recording decodes to an empty array, not None."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"")
    decoded = _decode_wav_to_float32(buf.getvalue())
    assert decoded is not None
    assert decoded.size == 0


def test_transcribe_returns_empty_when_wav_format_wrong():
    """Bad WAV format doesn't reach the model — early return on mismatch."""
    wav_bytes = _make_wav_bytes(np.zeros(100, dtype=np.float32), sample_rate=44100)
    client = GemmaSTTClient()
    assert client.transcribe(wav_bytes) == ""


def test_transcribe_wires_audio_and_returns_decoded_text():
    """Happy path: audio array is fed through the processor, generated tokens
    past the prompt are decoded and stripped before return."""
    client = GemmaSTTClient()
    # Bypass the lazy loader with pre-wired mocks so no real model is touched.
    mock_processor = MagicMock()
    mock_processor.apply_chat_template.return_value = {
        "input_ids": MagicMock(shape=(1, 42)),
    }
    mock_processor.decode.return_value = "   Hello world   "
    # Make .to() on the inputs dict return itself so the call chain works
    mock_inputs = MagicMock()
    mock_inputs.__getitem__.return_value = MagicMock(shape=(1, 42))
    mock_inputs.to.return_value = mock_inputs
    mock_processor.apply_chat_template.return_value = mock_inputs

    mock_model = MagicMock()
    mock_model.device = "cpu"
    mock_model.dtype = None
    # Outputs: shape (1, 60) — 18 new tokens past the 42 input tokens
    mock_model.generate.return_value = [list(range(60))]

    client._processor = mock_processor
    client._model = mock_model

    wav_bytes = _make_wav_bytes(np.array([0.1, 0.2, 0.3], dtype=np.float32))
    result = client.transcribe(wav_bytes)

    assert result == "Hello world"
    # The audio was handed to the processor inside the chat template
    messages = mock_processor.apply_chat_template.call_args.args[0]
    content = messages[0]["content"]
    audio_block = [c for c in content if c.get("type") == "audio"][0]
    assert isinstance(audio_block["audio"], np.ndarray)


def test_transcribe_returns_empty_on_model_exception():
    """Any exception during inference is swallowed so the UI handler doesn't crash."""
    client = GemmaSTTClient()
    mock_processor = MagicMock()
    mock_processor.apply_chat_template.side_effect = RuntimeError("CUDA OOM")
    client._processor = mock_processor
    client._model = MagicMock()

    wav_bytes = _make_wav_bytes(np.array([0.1, 0.2, 0.3], dtype=np.float32))
    assert client.transcribe(wav_bytes) == ""


def test_warm_swallows_load_errors():
    """warm() is best-effort — a load failure logs but doesn't propagate."""
    client = GemmaSTTClient()
    with patch.object(client, "_load", side_effect=RuntimeError("no internet")):
        client.warm()   # must not raise


def test_model_id_defaults_to_e2b_it():
    """Default is the instruction-tuned E2B; only the -it variants have a
    chat template, which the multimodal processor needs to build the prompt."""
    assert GemmaSTTClient().model_id == "google/gemma-4-E2B-it"


def test_model_id_accepts_e4b_it():
    """E4B-it variant is selectable."""
    assert GemmaSTTClient(model_id="google/gemma-4-E4B-it").model_id == "google/gemma-4-E4B-it"


def test_quantize_4bit_defaults_off():
    """4-bit must be opt-in so plain selections don't silently require bitsandbytes."""
    assert GemmaSTTClient().quantize_4bit is False


def test_quantize_4bit_flag_is_stored():
    """Flag round-trips for _load() to consult when building BitsAndBytesConfig."""
    assert GemmaSTTClient(quantize_4bit=True).quantize_4bit is True
