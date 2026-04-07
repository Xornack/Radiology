import requests
from src.security.scrubber import scrub_text

class LLMClient:
    """
    Client for interacting with a local Llama/Qwen microservice (OpenAI-compatible).
    """
    def __init__(self, url: str):
        self.url = url
        self.prompt_template = (
            "Given the following radiology findings, generate a concise impression. "
            "Findings: {findings}\nImpression:"
        )

    def generate_impression(self, findings: str) -> str:
        """
        Scrubs findings for PHI, sends to LLM, and returns the impression.
        """
        # Step 3 requirement: Scrub before API call
        clean_findings = scrub_text(findings)
        
        prompt = self.prompt_template.format(findings=clean_findings)
        
        payload = {
            "prompt": prompt,
            "max_tokens": 150,
            "temperature": 0.1,
            "stop": ["\n"]
        }
        
        try:
            response = requests.post(self.url, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                # Handle OpenAI-style response
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("text", "").strip()
            return ""
        except Exception:
            return ""
