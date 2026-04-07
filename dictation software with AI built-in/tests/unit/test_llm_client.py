import pytest
from unittest.mock import patch, MagicMock
from src.ai.llm_client import LLMClient

def test_generate_impression_success():
    """
    Ensures that LLMClient sends findings and returns a summary.
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": [{"text": "Impression: Normal study."}]}
    
    with patch('requests.post', return_value=mock_response):
        client = LLMClient(url="http://localhost:8001/v1/completions")
        findings = "The lungs are clear."
        result = client.generate_impression(findings)
        
        assert "Normal study" in result

def test_generate_impression_scrubs_phi():
    """
    Step 3 requirement: Verify that PHI is scrubbed before the API call.
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": [{"text": "Summarized"}]}
    
    with patch('requests.post', return_value=mock_response) as mock_post:
        # Patch the scrubber where it is USED
        with patch('src.ai.llm_client.scrub_text', side_effect=lambda x: x.replace("John Doe", "[NAME]")) as mock_scrub:
            client = LLMClient(url="http://localhost:8001/v1/completions")
            raw_findings = "Patient John Doe has clear lungs."
            
            client.generate_impression(raw_findings)
            
            # Verify scrubber was called
            mock_scrub.assert_called_with(raw_findings)
            
            # Verify the payload sent to requests.post contains the scrubbed text, not the name
            sent_payload = mock_post.call_args[1]['json']
            assert "John Doe" not in str(sent_payload)
            assert "[NAME]" in str(sent_payload)
