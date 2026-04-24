import requests
from loguru import logger

from src.security.scrubber import scrub_text


# Synthesized from ACR practice-parameter guidance, RadioGraphics' "How to
# Create a Great Radiology Report," and JACR's prompting guide. The rules
# are explicit because a 3B-class model needs the anti-patterns spelled
# out — without them it tends to just rephrase the findings verbatim.
_DEFAULT_SYSTEM_PROMPT = (
    "You are an experienced radiologist writing the IMPRESSION section of "
    "a radiology report from a section of FINDINGS.\n\n"
    "An impression is NOT a restatement of findings. It is your synthesis: "
    "the clinical meaning of what was observed, prioritized by importance, "
    "with actionable recommendations only when warranted.\n\n"
    "Rules:\n"
    "- Output a numbered list, ordered by clinical significance "
    "(most important / most actionable first).\n"
    "- 1-5 items typical. Fewer is better. If the study is normal, one "
    "sentence is enough.\n"
    "- Each item is ONE sentence. Synthesize - do NOT copy phrases "
    "verbatim from the findings.\n"
    "- For abnormal findings, name the most likely diagnosis when the "
    "imaging supports one. Add a brief differential only when imaging "
    "is genuinely ambiguous (most likely first).\n"
    "- Add a specific recommendation (follow-up modality + interval, "
    "clinical correlation, tissue sampling, etc.) only when the finding "
    "warrants action.\n"
    "- Use direct language. Avoid hedging fillers like \"evidence of\" "
    "or \"appears to be\" unless truly warranted.\n"
    "- Do NOT invent findings that are not in the input.\n"
    "- Do NOT include patient names, MRN, dates, or any other identifiers.\n"
    "- Do NOT restate the findings section or include the heading "
    "\"Findings:\".\n"
    "- Output only the numbered impression. No preamble, no commentary, "
    "no apologies."
)


# One concrete user/assistant pair anchoring the synthesis-not-restatement
# behavior + recommendation pattern. Multi-turn few-shot beats embedding
# the example in the system prompt for chat-tuned models because it
# matches the template they were trained on.
_FEWSHOT_USER = (
    "FINDINGS:\n"
    "The right lower lobe shows a focal area of consolidation with "
    "surrounding ground-glass opacity. Small right pleural effusion is "
    "present. The left lung is clear. The cardiomediastinal silhouette "
    "is normal. No pneumothorax."
)

_FEWSHOT_ASSISTANT = (
    "1. Right lower lobe consolidation with adjacent ground-glass and "
    "small pleural effusion, most compatible with pneumonia.\n"
    "2. Recommend clinical correlation and follow-up imaging after "
    "treatment to confirm resolution."
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
                {"role": "user", "content": _FEWSHOT_USER},
                {"role": "assistant", "content": _FEWSHOT_ASSISTANT},
                {"role": "user", "content": f"FINDINGS:\n{clean_findings}"},
            ],
            "stream": False,
            # num_predict caps the response length. Ollama defaults to 128
            # tokens which can truncate a 5-point impression mid-sentence;
            # 256 is comfortable for the typical 1-5 item list.
            "options": {"temperature": 0.1, "num_predict": 256},
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
