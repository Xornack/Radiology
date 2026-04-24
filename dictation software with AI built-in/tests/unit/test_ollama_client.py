import requests
from unittest.mock import patch, MagicMock

from src.ai.ollama_client import OllamaClient


def test_generate_impression_success():
    """OllamaClient parses Ollama's chat response and returns the text."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "message": {"content": "1. Normal study."}
    }

    with patch("requests.post", return_value=mock_response):
        client = OllamaClient(
            url="http://localhost:11434/api/chat",
            model="qwen2.5:3b",
        )
        result = client.generate_impression("The lungs are clear.")

    assert "Normal study" in result


def test_generate_impression_scrubs_phi():
    """PHI must be scrubbed BEFORE the request leaves the process."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"message": {"content": "Summarized."}}

    with patch("requests.post", return_value=mock_response) as mock_post:
        with patch(
            "src.ai.ollama_client.scrub_text",
            side_effect=lambda x: x.replace("John Doe", "[NAME]"),
        ) as mock_scrub:
            client = OllamaClient(
                url="http://localhost:11434/api/chat",
                model="qwen2.5:3b",
            )
            client.generate_impression("Patient John Doe has clear lungs.")

    mock_scrub.assert_called_once()
    sent_payload = mock_post.call_args[1]["json"]
    serialized = str(sent_payload)
    assert "John Doe" not in serialized
    assert "[NAME]" in serialized


def test_generate_impression_returns_empty_on_connection_error():
    """No Ollama server -> graceful empty string, no exception."""
    with patch("requests.post", side_effect=requests.ConnectionError):
        client = OllamaClient(
            url="http://localhost:11434/api/chat",
            model="qwen2.5:3b",
        )
        result = client.generate_impression("findings")
    assert result == ""


def test_generate_impression_returns_empty_on_http_error():
    """Non-200 (e.g. 404 model not pulled) -> empty string."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = '{"error":"model qwen2.5:3b not found"}'

    with patch("requests.post", return_value=mock_response):
        client = OllamaClient(
            url="http://localhost:11434/api/chat",
            model="qwen2.5:3b",
        )
        result = client.generate_impression("findings")
    assert result == ""


def test_structure_report_success():
    """OllamaClient.structure_report parses the chat response and returns it."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "message": {"content": "EXAMINATION:\nCT chest.\n\n..."}
    }

    with patch("requests.post", return_value=mock_response):
        client = OllamaClient(
            url="http://localhost:11434/api/chat",
            model="qwen2.5:3b",
        )
        result = client.structure_report("Some freeform report text.")

    assert "EXAMINATION:" in result


def test_structure_report_scrubs_phi():
    """PHI must be scrubbed BEFORE the structuring request leaves the process."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"message": {"content": "Structured."}}

    with patch("requests.post", return_value=mock_response) as mock_post:
        with patch(
            "src.ai.ollama_client.scrub_text",
            side_effect=lambda x: x.replace("John Doe", "[NAME]"),
        ) as mock_scrub:
            client = OllamaClient(
                url="http://localhost:11434/api/chat",
                model="qwen2.5:3b",
            )
            client.structure_report("Patient John Doe has clear lungs.")

    mock_scrub.assert_called_once()
    sent_payload = mock_post.call_args[1]["json"]
    serialized = str(sent_payload)
    assert "John Doe" not in serialized
    assert "[NAME]" in serialized


def test_structure_report_returns_empty_on_connection_error():
    """No Ollama server -> graceful empty string, no exception."""
    with patch("requests.post", side_effect=requests.ConnectionError):
        client = OllamaClient(
            url="http://localhost:11434/api/chat",
            model="qwen2.5:3b",
        )
        result = client.structure_report("some text")
    assert result == ""


def test_structure_report_uses_larger_num_predict():
    """Six-section reports are longer than impressions; the request must
    set num_predict >= 1024 so FINDINGS doesn't truncate mid-sentence."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"message": {"content": "Structured."}}

    with patch("requests.post", return_value=mock_response) as mock_post:
        client = OllamaClient(
            url="http://localhost:11434/api/chat",
            model="qwen2.5:3b",
        )
        client.structure_report("some text")

    sent_payload = mock_post.call_args[1]["json"]
    assert sent_payload["options"]["num_predict"] >= 1024


def test_chat_payload_sets_keep_alive():
    """keep_alive pins the model in memory between calls, eliminating the
    20-30s VRAM reload tax. Regression guard — this field must not be
    dropped by future edits."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"message": {"content": "ok"}}

    with patch("requests.post", return_value=mock_response) as mock_post:
        client = OllamaClient(
            url="http://localhost:11434/api/chat",
            model="qwen2.5:3b",
        )
        client.generate_impression("findings")

    sent_payload = mock_post.call_args[1]["json"]
    assert "keep_alive" in sent_payload
    assert sent_payload["keep_alive"]  # non-empty duration string


def test_chat_returns_empty_on_ollama_error_in_200_body():
    """Ollama sometimes returns HTTP 200 with {"error": ...} instead of
    the expected {"message": {"content": ...}}. The client must log and
    return "" rather than crashing on the missing "message" key."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"error": "model 'qwen2.5:3b' not found"}

    with patch("requests.post", return_value=mock_response):
        client = OllamaClient(
            url="http://localhost:11434/api/chat",
            model="qwen2.5:3b",
        )
        result = client.generate_impression("findings")

    assert result == ""


def test_chat_streams_via_on_chunk_callback():
    """When on_chunk is provided, the client requests stream=True and
    forwards each delta to the callback as it arrives. The final
    concatenation is still returned."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    # Ollama stream format: NDJSON, one {"message": {"content": "..."}}
    # per line, terminated by a {"done": true} frame.
    mock_response.iter_lines.return_value = iter([
        b'{"message": {"content": "Hello "}, "done": false}',
        b'{"message": {"content": "world"}, "done": false}',
        b'{"message": {"content": ""}, "done": true}',
    ])

    received = []

    with patch("requests.post", return_value=mock_response) as mock_post:
        client = OllamaClient(
            url="http://localhost:11434/api/chat",
            model="qwen2.5:3b",
        )
        result = client.generate_impression("findings", on_chunk=received.append)

    assert received == ["Hello ", "world"]
    assert result == "Hello world"
    # stream=True must be set in the payload AND as a requests kwarg so
    # the HTTP layer doesn't buffer the full body.
    sent_payload = mock_post.call_args[1]["json"]
    assert sent_payload["stream"] is True
    assert mock_post.call_args[1].get("stream") is True
