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


# Synthesized from ACR Practice Parameter for Communication, RSNA RadReport
# template conventions, and the ESR position paper on structured reporting.
# Strict template: always emit all six headings, even when the source omits
# them — the user explicitly chose visible-gap behavior over a lazy template.
_STRUCTURE_SYSTEM_PROMPT = (
    "You are an experienced radiologist converting an unstructured "
    "radiology report into a STRUCTURED report using the ACR-standard "
    "six-section template.\n\n"
    "Output the report in EXACTLY this template, with all six headings "
    "present in this exact order, even when the source provides nothing "
    "for that section:\n\n"
    "EXAMINATION:\n"
    "CLINICAL HISTORY:\n"
    "TECHNIQUE:\n"
    "COMPARISON:\n"
    "FINDINGS:\n"
    "IMPRESSION:\n\n"
    "Rules:\n"
    "- Always emit all six headings in the order above.\n"
    "- Under any heading the source does not cover, write exactly:\n"
    "  Not provided\n"
    "- Within FINDINGS, organize content by anatomic system (e.g. for "
    "chest: lungs, mediastinum, heart, pleura, vessels, osseous "
    "structures, soft tissues). Do not invent an ordering for body "
    "parts the source does not mention.\n"
    "- Never invent content. Only re-organize and lightly rephrase what "
    "is already in the source.\n"
    "- If the source already contains an IMPRESSION section, preserve "
    "its content verbatim or near-verbatim. This is a structuring pass, "
    "not a re-synthesis pass.\n"
    "- Do not include patient names, MRN, dates, or any other identifiers.\n"
    "- Output only the structured report. No preamble, no commentary, "
    "no apologies."
)


# One concrete user/assistant pair anchoring the six-section format,
# the "Not provided" placeholder convention, and the do-not-synthesize
# rule (source has no impression -> output IMPRESSION is "Not provided"
# despite an obvious nodule that warrants one).
_STRUCTURE_FEWSHOT_USER = (
    "CT chest done today for cough. Compared to scan from January.\n"
    "The lungs are clear. There is a 9 mm solid nodule in the right "
    "upper lobe, new compared to the prior. Heart size is normal. No "
    "pleural effusion. No mediastinal lymphadenopathy. Bones look fine."
)

_STRUCTURE_FEWSHOT_ASSISTANT = (
    "EXAMINATION:\n"
    "CT chest.\n\n"
    "CLINICAL HISTORY:\n"
    "Cough.\n\n"
    "TECHNIQUE:\n"
    "Not provided\n\n"
    "COMPARISON:\n"
    "Prior CT chest from January.\n\n"
    "FINDINGS:\n"
    "Lungs: Clear. New 9 mm solid nodule in the right upper lobe.\n"
    "Mediastinum: No lymphadenopathy.\n"
    "Heart: Normal in size.\n"
    "Pleura: No pleural effusion.\n"
    "Osseous structures: Unremarkable.\n\n"
    "IMPRESSION:\n"
    "Not provided"
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

        Returns "" on any failure so the UI degrades gracefully — the
        orchestrator and main.py treat empty as "Impression failed".
        """
        clean_findings = scrub_text(findings)
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": _FEWSHOT_USER},
            {"role": "assistant", "content": _FEWSHOT_ASSISTANT},
            {"role": "user", "content": f"FINDINGS:\n{clean_findings}"},
        ]
        return self._chat(messages, num_predict=256)

    def structure_report(self, text: str) -> str:
        """Scrub PHI, ask Ollama to slot the freeform text into the ACR
        six-section template, return the structured string.

        Returns "" on any failure so main.py can show "Structuring failed"
        without modifying the editor's contents.
        """
        clean_text = scrub_text(text)
        messages = [
            {"role": "system", "content": _STRUCTURE_SYSTEM_PROMPT},
            {"role": "user", "content": _STRUCTURE_FEWSHOT_USER},
            {"role": "assistant", "content": _STRUCTURE_FEWSHOT_ASSISTANT},
            {"role": "user", "content": clean_text},
        ]
        # 1024 tokens covers a comfortable six-section report; 128 (the
        # Ollama default) would routinely truncate mid-FINDINGS.
        return self._chat(messages, num_predict=1024)

    def _chat(self, messages: list[dict], num_predict: int = 256) -> str:
        """POST a chat request to Ollama. Returns assistant content or "" on failure."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            # num_predict caps response length. Ollama defaults to 128
            # tokens which can truncate longer outputs mid-sentence;
            # callers pass an appropriate cap for their feature.
            "options": {"temperature": 0.1, "num_predict": num_predict},
        }

        try:
            response = requests.post(self.url, json=payload, timeout=60)
        except requests.ConnectionError:
            # Most common failure mode by far — Ollama not running.
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
