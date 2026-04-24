"""MedASR client tests — transformers/torch are lazy-imported inside _load_impl
so these run without the [medasr] extra installed."""
import io
import wave

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from src.ai.medasr_stt_client import MedASRSTTClient, _expand_medasr_tags


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
    assert MedASRSTTClient().transcribe(b"") == ""


def test_supports_streaming_is_true():
    """MedASR is 105M — small enough for 1.5s live partials on GPU."""
    assert MedASRSTTClient.supports_streaming is True


def test_default_model_id_is_google_medasr():
    assert MedASRSTTClient().model_id == "google/medasr"


def test_custom_model_id_accepted():
    client = MedASRSTTClient(model_id="google/medasr-v2")
    assert client.model_id == "google/medasr-v2"


def test_wrong_sample_rate_returns_empty_string():
    """Non-16kHz audio is rejected by the shared WAV validator before the
    model runs — user never sees a confusing sample-rate error at inference."""
    bad = _wav(np.zeros(100, dtype=np.float32), sr=44100)
    assert MedASRSTTClient().transcribe(bad) == ""


def test_transcribe_wires_audio_and_returns_decoded_text():
    """Happy path: audio → processor → model.generate → batch_decode → stripped."""
    client = MedASRSTTClient()
    # Pre-wire processor + model so _load() short-circuits and no real
    # transformers/torch import happens.
    mock_inputs = MagicMock()
    mock_inputs.to.return_value = mock_inputs
    mock_processor = MagicMock(return_value=mock_inputs)
    mock_processor.batch_decode.return_value = ["  Chest X-ray is normal.  "]
    mock_model = MagicMock()
    mock_model.device = "cpu"
    mock_model.generate.return_value = [[1, 2, 3]]
    client._processor = mock_processor
    client._model = mock_model

    result = client.transcribe(_wav(np.array([0.1, 0.2, 0.3], dtype=np.float32)))

    assert result == "Chest X-ray is normal."
    # Audio was fed to the processor with the expected sample rate and dtype.
    call_args = mock_processor.call_args
    audio_arg = call_args.args[0]
    assert isinstance(audio_arg, np.ndarray)
    assert audio_arg.dtype == np.float32
    assert call_args.kwargs["sampling_rate"] == 16000
    # Special tokens must be stripped — otherwise `</s>` (emitted at every
    # pause by MedASR) leaks into the editor.
    assert mock_processor.batch_decode.call_args.kwargs.get(
        "skip_special_tokens"
    ) is True


def test_transcribe_strips_medasr_tag_braces():
    """The client strips `{...}` braces; the downstream punctuation pipeline
    is responsible for mapping the spoken words to glyphs so every tag the
    Whisper path handles (period, comma, question mark, new paragraph, …)
    just works here too."""
    client = MedASRSTTClient()
    mock_inputs = MagicMock()
    mock_inputs.to.return_value = mock_inputs
    mock_processor = MagicMock(return_value=mock_inputs)
    mock_processor.batch_decode.return_value = [
        "test the model {period} is it fast {question mark} "
        "{new paragraph}findings {colon} normal"
    ]
    mock_model = MagicMock()
    mock_model.device = "cpu"
    mock_model.generate.return_value = [[1]]
    client._processor = mock_processor
    client._model = mock_model

    result = client.transcribe(_wav(np.array([0.1], dtype=np.float32)))

    assert result == (
        "test the model period is it fast question mark "
        "new paragraph findings colon normal"
    )


def test_client_plus_apply_punctuation_converts_question_mark_tag():
    """End-to-end: a MedASR `{question mark}` tag must become `?` after
    the client hands off to the shared punctuation pipeline."""
    from src.engine.punctuation import apply_punctuation
    client = MedASRSTTClient()
    mock_inputs = MagicMock()
    mock_inputs.to.return_value = mock_inputs
    mock_processor = MagicMock(return_value=mock_inputs)
    mock_processor.batch_decode.return_value = ["is it clear {question mark}"]
    mock_model = MagicMock()
    mock_model.device = "cpu"
    mock_model.generate.return_value = [[1]]
    client._processor = mock_processor
    client._model = mock_model

    raw = client.transcribe(_wav(np.array([0.1], dtype=np.float32)))
    cleaned = apply_punctuation(raw, strip_inferred=False)

    assert cleaned == "Is it clear?"


@pytest.mark.parametrize("raw,expected", [
    # The helper strips braces; it does NOT convert words to glyphs — that
    # lives in `punctuation._substitute_tokens` and is shared across engines.
    ("foo {period} bar", "foo period bar"),
    ("foo {comma} bar {comma} baz", "foo comma bar comma baz"),
    ("lungs {colon} clear", "lungs colon clear"),
    ("part one {new paragraph} part two", "part one new paragraph part two"),
    ("one {period} {new paragraph} two", "one period new paragraph two"),
    ("is it clear {question mark}", "is it clear question mark"),
    # Tag flush against neighbors: padding keeps the words separable.
    ("word{period}next", "word period next"),
    ("only one {period}", "only one period"),
    ("{period} foo", "period foo"),
    ("  plain text  ", "plain text"),
    ("", ""),
])
def test_expand_medasr_tags_strips_braces(raw, expected):
    assert _expand_medasr_tags(raw) == expected


def test_medasr_flags_itself_as_emitting_punctuation():
    """The text pipeline's Whisper-style punctuation stripper would erase every
    period and comma we just expanded from `{period}` / `{comma}`. The flag
    is how MedASR opts out of that stripping."""
    assert MedASRSTTClient.emits_punctuation is True


def test_transcribe_returns_empty_when_decoder_produces_no_output():
    """batch_decode returning [] must degrade to an empty string, not IndexError."""
    client = MedASRSTTClient()
    mock_inputs = MagicMock()
    mock_inputs.to.return_value = mock_inputs
    mock_processor = MagicMock(return_value=mock_inputs)
    mock_processor.batch_decode.return_value = []
    mock_model = MagicMock()
    mock_model.device = "cpu"
    mock_model.generate.return_value = [[]]
    client._processor = mock_processor
    client._model = mock_model

    assert client.transcribe(_wav(np.array([0.1], dtype=np.float32))) == ""


def test_transcribe_swallows_model_exceptions():
    """Any inference failure is swallowed by the base class and returns ''."""
    client = MedASRSTTClient()
    mock_inputs = MagicMock()
    mock_inputs.to.return_value = mock_inputs
    mock_processor = MagicMock(return_value=mock_inputs)
    mock_model = MagicMock()
    mock_model.device = "cpu"
    mock_model.generate.side_effect = RuntimeError("CUDA OOM")
    client._processor = mock_processor
    client._model = mock_model

    assert client.transcribe(_wav(np.array([0.1], dtype=np.float32))) == ""


def test_warm_swallows_load_errors():
    """warm() is best-effort — a missing extra (or HF auth) logs but doesn't raise."""
    client = MedASRSTTClient()
    with patch.object(client, "_load", side_effect=ImportError("no transformers")):
        client.warm()   # must not raise
