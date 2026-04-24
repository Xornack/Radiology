# Structure Report Button Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Structure Report button next to Generate Impression that replaces freeform editor text with the ACR-standard six-section structured template, reusing the existing Ollama pipeline.

**Architecture:** Extend `OllamaClient` with a `structure_report` method, after first refactoring its HTTP/error/parse code into a private `_chat(messages, num_predict)` helper so `generate_impression` and `structure_report` share transport. Mirror the existing button-wiring pattern: orchestrator delegate + profiler timer, MainWindow button + callback hook, main.py handler.

**Tech Stack:** Python 3.13, PyQt6, `requests`, `pytest`, `loguru`. Local Ollama (`qwen2.5:3b` default) at `http://localhost:11434/api/chat`.

**Spec:** `docs/superpowers/specs/2026-04-23-structure-report-design.md`

---

## File Structure

**Modify:**
- `src/ai/ollama_client.py` — extract `_chat` helper, add `structure_report` + new system-prompt and few-shot constants.
- `src/core/orchestrator.py` — add `structure_report(text) -> str` with profiler timing.
- `src/ui/main_window.py` — add `Structure Report` button, `on_structure_report` callback hook, lock during recording.
- `src/main.py` — add `do_structure_report` handler wired to `window.on_structure_report`.
- `tests/unit/test_ollama_client.py` — four new tests.
- `tests/unit/test_orchestrator.py` — two new tests.

**No new files. No deleted files.**

---

## Task 0: Preflight

- [ ] **Step 1: Confirm clean working tree**

Run from project subdir (`dictation software with AI built-in/`):
```bash
git status
```
Expected: `nothing to commit, working tree clean`. The previous Ollama POC slice is fully merged.

If the tree is dirty, stop and ask the user before proceeding.

---

## Task 1: Failing tests for OllamaClient.structure_report

**Files:**
- Modify: `tests/unit/test_ollama_client.py` (append four tests at end of file)

- [ ] **Step 1: Append the four failing tests**

Open `tests/unit/test_ollama_client.py` and append (after the last existing test) exactly:

```python


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
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_ollama_client.py -v -k structure`
Expected: All four tests **FAIL** with `AttributeError: 'OllamaClient' object has no attribute 'structure_report'`.

- [ ] **Step 3: Run the existing tests to confirm we haven't broken them**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_ollama_client.py -v -k "not structure"`
Expected: All four existing impression tests still **PASS**.

- [ ] **Step 4: Commit the failing tests**

```bash
git add tests/unit/test_ollama_client.py
git commit -m "test: failing tests for OllamaClient.structure_report"
```

---

## Task 2: Refactor — extract `_chat` helper

The new `structure_report` will share HTTP/error/parse logic with `generate_impression`. Extract it first as a refactor that leaves the impression behavior byte-equivalent.

**Files:**
- Modify: `src/ai/ollama_client.py`

- [ ] **Step 1: Replace the `generate_impression` method body with a refactored version that delegates to a new `_chat` helper**

Open `src/ai/ollama_client.py`. Replace the entire `generate_impression` method (currently the only method on `OllamaClient` besides `__init__`) with both a refactored `generate_impression` AND a new `_chat` helper. The final structure inside the class becomes:

```python
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
```

The full behavior contract — same model, `temperature=0.1`, `num_predict=256`, `scrub_text` call before payload, empty-string on failure, identical log messages — must be preserved byte-equivalently. The four existing impression tests will catch any drift.

- [ ] **Step 2: Run the impression tests to verify byte-equivalent behavior**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_ollama_client.py -v -k "not structure"`
Expected: All four existing impression tests still **PASS**.

- [ ] **Step 3: Commit the refactor**

```bash
git add src/ai/ollama_client.py
git commit -m "refactor(ollama): extract _chat helper for shared HTTP/error/parse"
```

---

## Task 3: Implement OllamaClient.structure_report

**Files:**
- Modify: `src/ai/ollama_client.py`

- [ ] **Step 1: Add the structuring constants at module level**

In `src/ai/ollama_client.py`, after the existing `_FEWSHOT_USER` and `_FEWSHOT_ASSISTANT` constants near the top of the file, append three new module-level constants:

```python


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
```

- [ ] **Step 2: Add the `structure_report` method to `OllamaClient`**

In the same file, inside the `OllamaClient` class, add `structure_report` immediately AFTER `generate_impression` and BEFORE `_chat`:

```python
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
```

- [ ] **Step 3: Run all OllamaClient tests to verify both impression and structure pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_ollama_client.py -v`
Expected: All eight tests **PASS** (four impression, four structure).

- [ ] **Step 4: Commit**

```bash
git add src/ai/ollama_client.py
git commit -m "feat(ollama): structure_report builds ACR six-section reports"
```

---

## Task 4: Add `structure_report` to `DictationOrchestrator`

**Files:**
- Modify: `src/core/orchestrator.py`
- Modify: `tests/unit/test_orchestrator.py` (append two tests at end of file)

- [ ] **Step 1: Append the two failing orchestrator tests**

Open `tests/unit/test_orchestrator.py` and append at end of file (after the last existing test):

```python


def test_structure_report_delegates_to_llm_client():
    """Orchestrator.structure_report calls the LLM client's structure_report
    and returns its result."""
    from unittest.mock import MagicMock
    from src.core.orchestrator import DictationOrchestrator

    mock_llm = MagicMock()
    mock_llm.structure_report.return_value = "EXAMINATION:\nCT chest.\n..."

    orchestrator = DictationOrchestrator(
        recorder=MagicMock(),
        stt_client=MagicMock(),
        wedge=MagicMock(),
        llm_client=mock_llm,
    )

    result = orchestrator.structure_report("freeform report text")

    assert "EXAMINATION" in result
    mock_llm.structure_report.assert_called_once_with("freeform report text")


def test_structure_report_returns_empty_when_no_llm_client():
    """Orchestrator with no llm_client returns "" without crashing."""
    from unittest.mock import MagicMock
    from src.core.orchestrator import DictationOrchestrator

    orchestrator = DictationOrchestrator(
        recorder=MagicMock(),
        stt_client=MagicMock(),
        wedge=MagicMock(),
        llm_client=None,
    )

    result = orchestrator.structure_report("any text")
    assert result == ""
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_orchestrator.py -v -k structure_report`
Expected: Both tests **FAIL** with `AttributeError: 'DictationOrchestrator' object has no attribute 'structure_report'`.

- [ ] **Step 3: Add the `structure_report` method to the orchestrator**

In `src/core/orchestrator.py`, immediately AFTER the existing `generate_impression` method (the very last method on the class), append:

```python
    def structure_report(self, text: str) -> str:
        """Ask the LLM client to convert freeform text into the ACR
        six-section template. Time the round-trip via the profiler.

        Returns "" if no LLM client is configured. The profiler timer
        logs how expensive the longer ~1024-token output is so the
        user can decide whether to switch to a larger / faster model.
        """
        if not self.llm_client:
            logger.warning(
                "structure_report called but no LLM client is configured."
            )
            return ""
        if self.profiler:
            self.profiler.start("structure_report")
        try:
            return self.llm_client.structure_report(text)
        finally:
            if self.profiler:
                total = self.profiler.stop("structure_report")
                logger.info(f"Report structuring: {total:.2f}s")
```

- [ ] **Step 4: Run the orchestrator tests to verify all pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_orchestrator.py -v`
Expected: All tests **PASS** (28 existing + 2 new = 30).

- [ ] **Step 5: Commit**

```bash
git add src/core/orchestrator.py tests/unit/test_orchestrator.py
git commit -m "feat(orchestrator): structure_report delegate with profiler timing"
```

---

## Task 5: Add the Structure Report button to MainWindow

**Files:**
- Modify: `src/ui/main_window.py`

- [ ] **Step 1: Add the `on_structure_report` callback hook**

In `src/ui/main_window.py`, find the line:
```python
        self.on_generate_impression: Optional[Callable[[], None]] = None
```
(currently at line 34). Add immediately AFTER it:
```python
        self.on_structure_report: Optional[Callable[[], None]] = None
```

- [ ] **Step 2: Add the Structure Report button to the action bar**

In the same file, find the block that adds `self.impression_btn` to the action bar (currently around line 235-239):
```python
        self.impression_btn = QPushButton("Generate Impression")
        self.impression_btn.setObjectName("impressionBtn")
        self.impression_btn.setToolTip("Summarize the findings into an impression")
        self.impression_btn.clicked.connect(self._on_impression_clicked)
        ab.addWidget(self.impression_btn)
```

Add immediately AFTER `ab.addWidget(self.impression_btn)`:
```python

        self.structure_btn = QPushButton("Structure Report")
        self.structure_btn.setObjectName("structureBtn")
        self.structure_btn.setToolTip(
            "Replace the editor contents with the ACR six-section "
            "structured template (Ctrl+Z to undo)"
        )
        self.structure_btn.clicked.connect(self._on_structure_clicked)
        ab.addWidget(self.structure_btn)
```

- [ ] **Step 3: Add the `_on_structure_clicked` handler**

In the same file, find the `_on_impression_clicked` method (currently around line 279-281):
```python
    def _on_impression_clicked(self):
        if self.on_generate_impression is not None:
            self.on_generate_impression()
```

Add immediately AFTER it:
```python

    def _on_structure_clicked(self):
        if self.on_structure_report is not None:
            self.on_structure_report()
```

- [ ] **Step 4: Lock the new button during recording**

In the same file, find the `set_recording_state` method, specifically the line:
```python
        self.impression_btn.setEnabled(not recording)
```
(currently around line 423). Add immediately AFTER it:
```python
        self.structure_btn.setEnabled(not recording)
```

- [ ] **Step 5: Run the MainWindow tests to confirm no regression**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_main_window.py -v`
Expected: all existing tests still **PASS**. (The new button is purely additive — it shouldn't break any existing assertions.)

- [ ] **Step 6: Commit**

```bash
git add src/ui/main_window.py
git commit -m "feat(ui): add Structure Report button next to Generate Impression"
```

---

## Task 6: Wire `do_structure_report` in main.py

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: Add the handler immediately after `do_generate_impression`**

In `src/main.py`, find the block that defines `do_generate_impression` and wires it to `window.on_generate_impression` (currently around line 293-311):
```python
    def do_generate_impression():
        ...

    window.on_generate_impression = do_generate_impression
```

Add immediately AFTER `window.on_generate_impression = do_generate_impression`:
```python

    # Structure Report — replaces editor contents with the ACR six-section
    # template via the same Ollama pipeline. Editor is left untouched on
    # failure so a network blip can't destroy the user's text. Ctrl+Z
    # reverts the replacement via QTextEdit's built-in undo stack.
    def do_structure_report():
        text = window.get_findings().strip()
        if not text:
            window.set_status("No text to structure", "#f9e2af")
            return
        window.set_status("Structuring report...", "#89b4fa")
        window.structure_btn.setEnabled(False)
        try:
            structured = orchestrator.structure_report(text)
        finally:
            window.structure_btn.setEnabled(True)
        if structured:
            window.editor.setPlainText(structured)
            window.set_status("Ready")
        else:
            window.set_status("Structuring failed", "#f38ba8")

    window.on_structure_report = do_structure_report
```

- [ ] **Step 2: Smoke-import main**

Run: `.venv/Scripts/python.exe -c "import src.main"`
Expected: no error, no output.

- [ ] **Step 3: Commit**

```bash
git add src/main.py
git commit -m "feat(main): wire Structure Report button to orchestrator"
```

---

## Task 7: Full test suite green

- [ ] **Step 1: Run the full suite (excluding the three pre-existing pyinstrument-broken files)**

Run:
```bash
.venv/Scripts/python.exe -m pytest \
  --ignore=tests/unit/test_profiling_harness.py \
  --ignore=tests/unit/test_profiling_scenarios.py \
  --ignore=tests/unit/test_profile_pipeline_dryrun.py
```
Expected: **328 passed** (322 from previous slice + 4 new ollama_client + 2 new orchestrator).

- [ ] **Step 2: If anything is red, stop and diagnose**

Common causes:
- The `_chat` refactor accidentally changed payload shape — re-read Task 2 Step 1 against the current file.
- A copy/paste landed `_FEWSHOT_USER` content in the structuring few-shot or vice versa — re-read Task 3 Step 1.
- `set_recording_state` has stale state for the new button — re-read Task 5 Step 4.

---

## Task 8: Manual smoke test

This task is for the human user — the agent should pause here, walk the user through it, and wait for confirmation before continuing to readability.

- [ ] **Step 1: Start Ollama and confirm the model**

```bash
ollama serve   # if not already running
ollama list    # confirm qwen2.5:3b is present (it should be from the previous slice)
```

- [ ] **Step 2: Launch the app**

```bash
python -m src.main
```

Expected: app window appears with the new **Structure Report** button visible to the right of **Generate Impression** in the action bar.

- [ ] **Step 3: Happy path**

1. Type or dictate this freeform paragraph into the editor:
   > "CT chest done today for cough. The lungs are clear. There is a 9mm right upper lobe nodule, new compared to January. Heart normal. No effusion."
2. Click **Structure Report**.
3. Within ~few seconds (slower on the very first call after Ollama loads the model), the editor contents are REPLACED with a six-section template. Each heading appears (EXAMINATION:, CLINICAL HISTORY:, TECHNIQUE:, COMPARISON:, FINDINGS:, IMPRESSION:). Headings the source didn't cover (TECHNIQUE, IMPRESSION) read `Not provided`. FINDINGS is grouped by anatomic system.
4. Status bar shows "Ready".
5. Loguru log shows `Report structuring: X.XXs`.

- [ ] **Step 4: Undo**

Press **Ctrl+Z**. The original freeform paragraph reappears in the editor (QTextEdit's built-in undo restores the prior state in one step).

- [ ] **Step 5: Cold-failure path**

1. Stop `ollama serve` (Ctrl-C the server, or `taskkill /IM ollama.exe /F` on Windows).
2. Click **Structure Report** again.
3. Status bar shows "Structuring failed".
4. Editor contents are UNCHANGED.
5. Log contains the connection-refused hint.
6. Button is re-enabled and clickable.

- [ ] **Step 6: Empty path**

1. Click **Clear**, then click **Structure Report** with the editor empty.
2. Status reads "No text to structure". No LLM call (nothing in the log about Ollama).

- [ ] **Step 7: Confirm with the user**

Wait for the user to confirm all four scenarios pass. If any misbehave, fix the underlying issue and re-run the suite.

---

## Task 9: Readability pass

After the smoke test passes.

**Files:**
- Modify (only if anything needs tidying): `src/ai/ollama_client.py`

- [ ] **Step 1: Inspect OllamaClient for tidiness**

Open `src/ai/ollama_client.py` and check:
- No orphaned imports.
- `_chat` has a one-line docstring describing its single responsibility (POST + parse).
- `generate_impression` and `structure_report` look syntactically parallel: both scrub, both build a four-message list (system + user-fewshot + assistant-fewshot + real user), both call `self._chat(messages, num_predict=...)`. If either is missing scrubbing, has different error handling, or doesn't follow the four-message pattern, fix it.
- No commented-out leftovers from the Task 2 refactor.

- [ ] **Step 2: If you found anything to tidy, run the full suite to confirm no regression**

Run:
```bash
.venv/Scripts/python.exe -m pytest \
  --ignore=tests/unit/test_profiling_harness.py \
  --ignore=tests/unit/test_profiling_scenarios.py \
  --ignore=tests/unit/test_profile_pipeline_dryrun.py
```
Expected: 328 passed.

- [ ] **Step 3: Commit any tidying**

```bash
git add src/ai/ollama_client.py
git commit -m "chore(ollama): readability pass on structure/impression parallelism"
```

If nothing needed tidying, skip the commit and note it in the final report.

---

## Task 10: Final verification

- [ ] **Step 1: Run the full suite one last time**

Run:
```bash
.venv/Scripts/python.exe -m pytest \
  --ignore=tests/unit/test_profiling_harness.py \
  --ignore=tests/unit/test_profiling_scenarios.py \
  --ignore=tests/unit/test_profile_pipeline_dryrun.py
```
Expected: 328 passed.

- [ ] **Step 2: Show the commit sequence for this slice**

Run: `git log --oneline 2ca0df6..HEAD`
Expected: a clean sequence like:
```
chore(ollama): readability pass on structure/impression parallelism   (optional)
feat(main): wire Structure Report button to orchestrator
feat(ui): add Structure Report button next to Generate Impression
feat(orchestrator): structure_report delegate with profiler timing
feat(ollama): structure_report builds ACR six-section reports
refactor(ollama): extract _chat helper for shared HTTP/error/parse
test: failing tests for OllamaClient.structure_report
```

- [ ] **Step 3: Done — report to the user**

Report:
- Tests green: yes / no.
- Smoke test green: yes / no (per Task 8 four scenarios).
- Approximate cold and warm latency observed for `Report structuring`.
- Any deviations from the plan, with reason.

---

## Summary

This plan delivers, in ten bite-sized tasks:

1. A **Structure Report** button that replaces freeform editor text with the ACR-standard six-section structured template (EXAMINATION, CLINICAL HISTORY, TECHNIQUE, COMPARISON, FINDINGS, IMPRESSION).
2. Six new tests covering the new method's contract: parsing, PHI scrubbing, connection-failure graceful degrade, larger `num_predict`, orchestrator delegation, and no-client safety.
3. A small `_chat` refactor on `OllamaClient` so future LLM features inherit the same HTTP/error/parse code without duplication.
4. Profiler instrumentation so per-click structuring latency is visible in the log.
5. A non-destructive UX: empty source short-circuits, failure leaves the editor untouched, Ctrl+Z reverts the replacement.

After this slice, the same `_chat` helper is the natural foundation for the next AI buttons (macros, readback, field-template expansion).
