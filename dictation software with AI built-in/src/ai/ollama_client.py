import requests
from loguru import logger

from src.security.scrubber import scrub_text


_DEFAULT_SYSTEM_PROMPT = (
    "You are a radiologist's assistant. Given a section of findings, "
    "write a concise impression in numbered bullet points. Do not invent "
    "findings that are not in the input. Do not include patient identifiers."
)


class OllamaClient:
    """Local LLM client backed by an Ollama server (chat endpoint)."""

    def __init__(
        self,
        url: str,
        model: str,
        system_prompt: str | None = None,
    ):
        self.url = url
        self.model = model
        self.system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT

    def generate_impression(self, findings: str) -> str:
        """Scrub PHI, ask Ollama for an impression, return the text.

        Returns "" on any failure so the UI degrades gracefully — matches
        the contract main.py and the orchestrator already expect from the
        previous LLMClient.
        """
        clean_findings = scrub_text(findings)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": (
                    f"Findings:\n{clean_findings}\n\n"
                    "Provide a concise impression."
                )},
            ],
            "stream": False,
            "options": {"temperature": 0.1},
        }

        try:
            response = requests.post(self.url, json=payload, timeout=60)
        except requests.ConnectionError:
            # Most common failure mode by far — Ollama not running.
            # Hint the fix in the log so the user doesn't have to guess.
            logger.warning(
                f"Ollama connection refused at {self.url} — "
                "is `ollama serve` running?"
            )
            return ""
        except requests.Timeout:
            logger.warning(
                "Ollama request timed out after 60s — cold model load? "
                "Consider OLLAMA_KEEP_ALIVE=24h in your shell."
            )
            return ""
        except Exception as e:
            logger.error(f"Ollama request failed unexpectedly: {e}")
            return ""

        if response.status_code != 200:
            # Truncate the body so a misbehaving server can't spam the log
            # but a missing-model 404 is still obvious at a glance.
            body_excerpt = response.text[:200]
            logger.warning(
                f"Ollama returned HTTP {response.status_code}: {body_excerpt!r}"
            )
            return ""

        try:
            data = response.json()
            return data["message"]["content"].strip()
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(
                f"Ollama response malformed ({type(e).__name__}): {e}"
            )
            return ""
