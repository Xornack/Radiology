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
