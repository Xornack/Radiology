# Ollama-Backed Impression POC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the existing Generate Impression button to a locally running Ollama model (`qwen2.5:3b` by default) via the chat endpoint, end-to-end, with PHI scrubbing, error handling, and unit tests.

**Architecture:** New `OllamaClient` in `src/ai/ollama_client.py` mirrors the interface of the existing `LLMClient` (`generate_impression(findings: str) -> str`). `main.py` constructs `OllamaClient` instead of `LLMClient`. The orchestrator and UI need zero changes because both clients share the empty-string-on-failure contract. After end-to-end verification, the old `LLMClient` and its settings/tests are deleted.

**Tech Stack:** Python 3.13, PyQt6, `requests`, `pytest`, `loguru`. Ollama running locally on `localhost:11434`.

**Spec:** `docs/superpowers/specs/2026-04-23-ollama-impression-poc-design.md`

---

## File Structure

**Create:**
- `src/ai/ollama_client.py` — new client; one class, ~60 lines; talks to Ollama `/api/chat`.
- `tests/unit/test_ollama_client.py` — unit tests mirroring `tests/unit/test_llm_client.py`.

**Modify:**
- `src/utils/settings.py` — add `ollama_url`, `ollama_model`; remove `llm_url` in cleanup pass.
- `src/main.py` — swap `LLMClient` import + constructor for `OllamaClient`.
- `src/core/orchestrator.py` — wrap `generate_impression` with profiler timing.

**Delete (cleanup pass):**
- `src/ai/llm_client.py`
- `tests/unit/test_llm_client.py`

---

## Task 0: Preflight — handle pre-existing dirty work

The working tree has pre-existing modifications in `src/main.py` and `src/core/orchestrator.py` (and two test files). This plan modifies both of those source files. Decide before starting whether to keep those changes — if they're stale or unrelated, stash them; if they're real WIP, commit them first so this plan's commits stay focused.

- [ ] **Step 1: Inspect pending changes**

Run from the project subdir (`dictation software with AI built-in/`):
```bash
git status
git diff src/main.py src/core/orchestrator.py tests/integration/test_streaming_pipeline.py tests/unit/test_orchestrator.py
```

Expected: see ~83 lines of changes across those four files, dating from before this plan started.

- [ ] **Step 2: Resolve the dirty tree**

Pick one:
- **Commit them** if they are intentional in-progress work:
  ```bash
  git add src/main.py src/core/orchestrator.py tests/integration/test_streaming_pipeline.py tests/unit/test_orchestrator.py
  git commit -m "wip: pre-existing local changes (pre-Ollama POC)"
  ```
- **Stash them** if you want to evaluate later:
  ```bash
  git stash push -m "pre-Ollama POC WIP" src/main.py src/core/orchestrator.py tests/integration/test_streaming_pipeline.py tests/unit/test_orchestrator.py
  ```
- **Discard them** ONLY if you have confirmed with the user that the changes are unwanted.

- [ ] **Step 3: Confirm clean working tree for files this plan touches**

Run: `git status`
Expected: `src/main.py`, `src/core/orchestrator.py`, `src/utils/settings.py` are clean (no pending changes). Other unrelated dirty files are fine.

---

## Task 1: Create the failing OllamaClient unit tests

**Files:**
- Create: `tests/unit/test_ollama_client.py`

- [ ] **Step 1: Write the four failing tests**

Create `tests/unit/test_ollama_client.py` with this exact content:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/unit/test_ollama_client.py -v`
Expected: All four tests **FAIL** with `ModuleNotFoundError: No module named 'src.ai.ollama_client'`.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/unit/test_ollama_client.py
git commit -m "test: failing tests for OllamaClient (POC)"
```

---

## Task 2: Implement OllamaClient to make the tests pass

**Files:**
- Create: `src/ai/ollama_client.py`

- [ ] **Step 1: Write the client**

Create `src/ai/ollama_client.py` with this exact content:

```python
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
```

- [ ] **Step 2: Run the tests to verify they pass**

Run: `pytest tests/unit/test_ollama_client.py -v`
Expected: All four tests **PASS**.

- [ ] **Step 3: Commit the implementation**

```bash
git add src/ai/ollama_client.py
git commit -m "feat: OllamaClient hits Ollama /api/chat for impressions"
```

---

## Task 3: Add Ollama settings

**Files:**
- Modify: `src/utils/settings.py`

- [ ] **Step 1: Add the two settings fields**

In `src/utils/settings.py`, inside `Settings.__init__`, add these two lines immediately after the existing `self.llm_url = ...` block (around line 71). Do not remove `self.llm_url` yet — the cleanup pass handles that after end-to-end verification:

```python
        self.ollama_url: str = os.getenv(
            "OLLAMA_URL", "http://localhost:11434/api/chat"
        )
        self.ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
```

- [ ] **Step 2: Sanity-check the import still loads**

Run: `python -c "from src.utils.settings import settings; print(settings.ollama_url, settings.ollama_model)"`
Expected: prints `http://localhost:11434/api/chat qwen2.5:3b`.

- [ ] **Step 3: Commit**

```bash
git add src/utils/settings.py
git commit -m "feat(settings): OLLAMA_URL and OLLAMA_MODEL with sensible defaults"
```

---

## Task 4: Swap main.py to construct OllamaClient

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: Replace the import**

In `src/main.py`, change line 12:

From:
```python
from src.ai.llm_client import LLMClient
```
To:
```python
from src.ai.ollama_client import OllamaClient
```

- [ ] **Step 2: Replace the constructor**

In `src/main.py`, change the `llm = ...` line (around line 35):

From:
```python
    llm = LLMClient(url=settings.llm_url)
```
To:
```python
    llm = OllamaClient(url=settings.ollama_url, model=settings.ollama_model)
```

- [ ] **Step 3: Smoke-import main**

Run: `python -c "import src.main"`
Expected: no error, no output. (The import shouldn't run `main()`.)

- [ ] **Step 4: Commit**

```bash
git add src/main.py
git commit -m "feat(main): construct OllamaClient instead of LLMClient"
```

---

## Task 5: Add profiler instrumentation to orchestrator.generate_impression

**Files:**
- Modify: `src/core/orchestrator.py:210-218`

- [ ] **Step 1: Replace the existing generate_impression body**

In `src/core/orchestrator.py`, replace the `generate_impression` method (lines 210-218) with:

```python
    def generate_impression(self, findings: str) -> str:
        """Ask the LLM client for an impression and time the round-trip.

        Returns "" if no LLM client is configured. The profiler timer
        logs cold-vs-warm Ollama latency so the user can see whether
        keep-alive tuning is needed.
        """
        if not self.llm_client:
            logger.warning(
                "generate_impression called but no LLM client is configured."
            )
            return ""
        if self.profiler:
            self.profiler.start("llm_impression")
        try:
            return self.llm_client.generate_impression(findings)
        finally:
            if self.profiler:
                total = self.profiler.stop("llm_impression")
                logger.info(f"Impression generation: {total:.2f}s")
```

- [ ] **Step 2: Run the orchestrator's existing unit tests to confirm no regression**

Run: `pytest tests/unit/test_orchestrator.py -v`
Expected: all existing tests still pass. (None of them depend on `generate_impression`'s body — they mock `llm_client`.)

- [ ] **Step 3: Commit**

```bash
git add src/core/orchestrator.py
git commit -m "feat(orchestrator): time impression round-trip via profiler"
```

---

## Task 6: Run the full test suite

- [ ] **Step 1: Run everything**

Run: `pytest -v`
Expected: full green. The new four tests pass; the old `test_llm_client.py` still passes (it doesn't reference any swapped code path); orchestrator/integration tests still pass.

- [ ] **Step 2: If anything is red, stop and diagnose**

Do not proceed to manual smoke testing or cleanup until the suite is green. Common causes:
- Forgot to import `OllamaClient` in `main.py`.
- Stale `.pyc` from a renamed file — try `find . -name "__pycache__" -type d | xargs rm -rf`.
- A pre-existing dirty file from Task 0 was left in a half-applied state.

---

## Task 7: Manual smoke test against a live Ollama

This task is for the human user — the agent should pause here, prompt the user to run through it, and wait for confirmation before proceeding to cleanup.

- [ ] **Step 1: Start Ollama and pull the model**

In a terminal:
```bash
ollama serve   # if not already running as a service
ollama pull qwen2.5:3b
```

Recommended (separate shell or system env): `OLLAMA_KEEP_ALIVE=24h` so the model stays warm.

- [ ] **Step 2: Launch the app**

```bash
python -m src.main
```

Expected: app window appears, no errors in the console.

- [ ] **Step 3: Generate an impression**

1. Type or dictate findings into the editor, e.g.:
   > "The lungs are clear. The heart is normal in size. No pleural effusion. No pneumothorax."
2. Click **Generate Impression**.
3. Within a few seconds (slower on the very first click while the model loads), `IMPRESSION: <text>` appears appended to the editor.
4. Status bar shows "Ready".
5. Loguru log shows `Impression generation: X.XXs`.

- [ ] **Step 4: Test cold-failure path**

1. Stop `ollama serve` (Ctrl-C the server, or `taskkill /IM ollama.exe /F` on Windows).
2. Click **Generate Impression** again.
3. Status bar shows "Impression failed".
4. Log contains: `Ollama connection refused at ... — is `ollama serve` running?`
5. The button is re-enabled and clickable again.

- [ ] **Step 5: Confirm with the user**

Wait for the user to confirm the smoke test passed before continuing. If anything misbehaved, fix the problem (likely in `ollama_client.py` or `main.py`) and re-run the suite.

---

## Task 8: Cleanup pass — delete old LLMClient

This task runs only after Task 7's smoke test passes. The old `LLMClient` is unreferenced once `main.py` is on `OllamaClient`.

**Files:**
- Delete: `src/ai/llm_client.py`
- Delete: `tests/unit/test_llm_client.py`
- Modify: `src/utils/settings.py` (remove `llm_url`)

- [ ] **Step 1: Confirm nothing else references LLMClient**

Run: `grep -rn "LLMClient\|llm_url" src/ tests/`
Expected: no matches in `src/` or `tests/` other than the files we're about to delete and `settings.py`'s `llm_url` line.

If something else matches (unlikely — main.py was the only consumer), stop and resolve before deleting.

- [ ] **Step 2: Delete the dead files**

```bash
git rm src/ai/llm_client.py tests/unit/test_llm_client.py
```

- [ ] **Step 3: Remove `llm_url` from settings**

In `src/utils/settings.py`, delete the three lines:
```python
        self.llm_url: str = os.getenv(
            "LLM_URL", "http://localhost:8001/v1/completions"
        )
```

- [ ] **Step 4: Run the full suite**

Run: `pytest -v`
Expected: full green. The deleted `test_llm_client.py` no longer runs; nothing else should have depended on it.

- [ ] **Step 5: Sanity-check the app still launches**

Run: `python -c "import src.main"`
Expected: no error.

- [ ] **Step 6: Commit cleanup**

```bash
git add src/utils/settings.py
git commit -m "chore: remove unused LLMClient and llm_url setting"
```

---

## Task 9: Final verification

- [ ] **Step 1: Run the full suite one last time**

Run: `pytest -v`
Expected: full green.

- [ ] **Step 2: Show the git log for the slice**

Run: `git log --oneline a93a1fe..HEAD`
Expected: a clean sequence of commits, roughly:
```
chore: remove unused LLMClient and llm_url setting
feat(orchestrator): time impression round-trip via profiler
feat(main): construct OllamaClient instead of LLMClient
feat(settings): OLLAMA_URL and OLLAMA_MODEL with sensible defaults
feat: OllamaClient hits Ollama /api/chat for impressions
test: failing tests for OllamaClient (POC)
```
(Plus the optional "wip" commit from Task 0 if you took that path.)

- [ ] **Step 3: Done — report to the user**

Report:
- Tests green: yes/no
- Smoke test green: yes/no
- Approximate cold and warm latency observed during smoke test
- Any deviations from the plan, with reason

---

## Summary

This plan delivers, in nine bite-sized tasks:
1. A real, locally-running impression generator (Ollama + qwen2.5:3b) wired to the existing button.
2. Four unit tests covering success, PHI scrubbing, connection failure, and HTTP failure.
3. Profiler instrumentation so the user can see per-click latency in the log.
4. A clean cleanup pass deleting the dead `LLMClient` and its config.

After this slice, adding more local-LLM features (macros, readback, field templates) is a matter of constructing a different request payload — the wiring pattern is proven.
