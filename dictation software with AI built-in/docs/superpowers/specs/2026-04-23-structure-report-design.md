# Structure Report Button Design

**Date:** 2026-04-23
**Status:** Design approved, ready for implementation plan
**Scope:** Single button that replaces unstructured text in the editor with an ACR-standard six-section structured report

## Goal

Add a **Structure Report** button next to **Generate Impression**. When clicked, the editor's current contents are sent to the local Ollama model and replaced with the same content reorganized into the canonical ACR-style six-section template (EXAMINATION, CLINICAL HISTORY, TECHNIQUE, COMPARISON, FINDINGS, IMPRESSION). Reuses the existing OllamaClient, settings, profiler, and PHI-scrubbing path established by the impression POC.

## Non-goals

- Modality-aware section ordering (chest CT vs brain MRI specialization). Generic ACR template only. Defer until real-world use shows which modalities matter most.
- Side-by-side preview / diff dialog. The button replaces editor contents in place; QTextEdit's built-in undo (Ctrl+Z) reverts.
- Re-synthesizing the impression. If the source has an existing impression section, preserve it. This is structuring, not re-summarization.
- New LLM client class. Extend existing OllamaClient.
- Any new env vars or settings. Reuse OLLAMA_URL and OLLAMA_MODEL.
- Inventing missing content. Empty sections render as `Not provided`, never fabricated text.
- Templates persisted to disk / RadReport library integration. Out of scope; future work.

## Architecture

```
[Structure Report button]
        |
        v
main.py do_structure_report()
        |
        v
DictationOrchestrator.structure_report(text)
        |- profiler.start("structure_report")
        v
OllamaClient.structure_report(text)
        |- scrub_text(text)
        |- builds messages [system, fewshot_user, fewshot_assistant, user]
        |- _chat(messages, num_predict=1024)
              |- POST /api/chat
              |- error handling -> ""
              |- parse response.message.content
        v
returns str -> main.py replaces editor.toPlainText() with the result
```

`OllamaClient` is refactored to extract a private `_chat(messages, num_predict)` helper so `generate_impression` and `structure_report` share the HTTP/error/parse/payload code without duplication.

## Components

### `OllamaClient` (`src/ai/ollama_client.py`) — additions

- **Refactor:** extract `_chat(messages: list[dict], num_predict: int = 256) -> str`. This wraps the payload assembly (model, messages, `stream=False`, `options.temperature=0.1`, `options.num_predict`), the `requests.post(...)`, the error-handling cascade, the HTTP-status check, and the JSON parsing. Returns `""` on any failure.
- **Refactor:** rewrite `generate_impression` to call `scrub_text` on its input, build its messages list (system + few-shot user + few-shot assistant + real user) and call `_chat(messages, num_predict=256)`. The full behavior contract — same model, same `temperature=0.1`, same `num_predict=256`, same scrub call before payload, same empty-string on failure — must be preserved byte-equivalently. The four existing impression unit tests must continue to pass without modification.
- **New:** `structure_report(text: str) -> str` — scrubs PHI, builds a messages list (system prompt + few-shot user/assistant pair + the user's report), calls `_chat(messages, num_predict=1024)`, returns the structured string or `""`.
- **New constants:**
  - `_STRUCTURE_SYSTEM_PROMPT` — see "The structuring prompt" below.
  - `_STRUCTURE_FEWSHOT_USER` — a freeform paragraph mixing chest CT findings with no headings.
  - `_STRUCTURE_FEWSHOT_ASSISTANT` — same content slotted into the six-section template, with `Not provided` for sections the source didn't cover.

### `DictationOrchestrator` (`src/core/orchestrator.py`)

- **New:** `structure_report(text: str) -> str` mirroring `generate_impression`:
  - Returns `""` if no `llm_client`.
  - Wraps the call with `profiler.start("structure_report")` / `stop` and logs `Report structuring: X.XXs`.

### `MainWindow` (`src/ui/main_window.py`)

- **New widget:** `self.structure_btn = QPushButton("Structure Report")` placed in the action bar **after** the Generate Impression button.
- **Same disable/enable lock** as `impression_btn` (off during recording, off while warming).
- **New callback hook:** `self.on_structure_report: Optional[Callable[[], None]] = None`, fired by an `_on_structure_clicked` method connected to the button.

### `main.py`

- New handler `do_structure_report` wired to `window.on_structure_report`:
  ```
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
      # Replace editor contents — Ctrl+Z reverts via QTextEdit's undo.
      window.editor.setPlainText(structured)
      window.set_status("Ready")
  else:
      window.set_status("Structuring failed", "#f38ba8")
  ```

The pattern intentionally matches `do_generate_impression` so future LLM-button features (macros, readback, etc.) follow the same shape.

## The structuring prompt

Synthesized from the same sources that informed the impression prompt — ACR Practice Parameter for Communication, RSNA RadReport templates, ESR position paper on structured reporting — plus the prompting principles in our `project_llm_prompting` memory.

### System prompt (rules)

```
You are an experienced radiologist converting an unstructured radiology
report into a STRUCTURED report using the ACR-standard six-section
template.

Output the report in EXACTLY this template, with all six headings
present in this exact order, even when the source provides nothing
for that section:

EXAMINATION:
CLINICAL HISTORY:
TECHNIQUE:
COMPARISON:
FINDINGS:
IMPRESSION:

Rules:
- Always emit all six headings in the order above.
- Under any heading the source does not cover, write exactly:
  Not provided
- Within FINDINGS, organize content by anatomic system (e.g. for chest:
  lungs, mediastinum, heart, pleura, vessels, osseous structures, soft
  tissues). Do not invent an ordering for body parts the source does
  not mention.
- Never invent content. Only re-organize and lightly rephrase what is
  already in the source.
- If the source already contains an IMPRESSION section, preserve its
  content verbatim or near-verbatim. This is a structuring pass, not
  a re-synthesis pass.
- Do not include patient names, MRN, dates, or any other identifiers.
- Output only the structured report. No preamble, no commentary, no
  apologies.
```

### Few-shot pair (one example)

**User (the freeform input):**
```
CT chest done today for cough. Compared to scan from January.
The lungs are clear. There is a 9 mm solid nodule in the right
upper lobe, new compared to the prior. Heart size is normal. No
pleural effusion. No mediastinal lymphadenopathy. Bones look fine.
```

**Assistant (the structured output):**
```
EXAMINATION:
CT chest.

CLINICAL HISTORY:
Cough.

TECHNIQUE:
Not provided

COMPARISON:
Prior CT chest from January.

FINDINGS:
Lungs: Clear. New 9 mm solid nodule in the right upper lobe.
Mediastinum: No lymphadenopathy.
Heart: Normal in size.
Pleura: No pleural effusion.
Osseous structures: Unremarkable.

IMPRESSION:
Not provided
```

This single example anchors:
- The exact six headings in order.
- `Not provided` as the placeholder string (verbatim).
- Anatomic ordering inside FINDINGS.
- The "do not synthesize an impression that isn't in the source" rule (source has none, so IMPRESSION is `Not provided` even though there's clearly a nodule that warrants one).

## Data flow

1. User dictates or pastes freeform text into the editor.
2. User clicks **Structure Report**.
3. `do_structure_report` reads `editor.toPlainText()`. If empty, status → "No text to structure", return.
4. Status → "Structuring report...". Button disabled.
5. Orchestrator calls `OllamaClient.structure_report(text)`.
6. Client scrubs PHI, builds messages list, POSTs to Ollama with `num_predict=1024`, parses, returns string (or `""`).
7. Profiler logs `Report structuring: X.XXs`.
8. main.py replaces `editor.setPlainText(structured)` if non-empty; status → "Ready". Otherwise status → "Structuring failed", editor unchanged.
9. Button re-enabled.

## Error handling

Same matrix as the impression button (delegated through `_chat`):

| Failure | Detection | Log | UI |
| --- | --- | --- | --- |
| Empty editor | string check before LLM call | none | "No text to structure" |
| Ollama not running | `requests.ConnectionError` | warn with hint | "Structuring failed" |
| Cold-load timeout | `requests.Timeout` after 60s | warn with keep-alive hint | "Structuring failed" |
| Model not pulled | HTTP 404 + body excerpt | warn | "Structuring failed" |
| Other HTTP error | non-200 | warn | "Structuring failed" |
| Malformed response | KeyError / JSONDecodeError | warn | "Structuring failed" |

On any failure the editor contents are **not modified** — the user's original text is preserved.

## Testing

### Unit tests in `tests/unit/test_ollama_client.py` (four new)

1. **`test_structure_report_success`** — mock 200 response, assert returned string contains the expected structured content.
2. **`test_structure_report_scrubs_phi`** — patch `scrub_text` to redact a name, assert the scrubbed form (not the original) is in the request payload.
3. **`test_structure_report_returns_empty_on_connection_error`** — mock `requests.ConnectionError`, assert `""`.
4. **`test_structure_report_uses_larger_num_predict`** — mock 200 response, inspect payload, assert `options.num_predict >= 1024`. Locks the contract that long structured reports won't be truncated.

### Unit tests in `tests/unit/test_orchestrator.py` (two new)

1. **`test_structure_report_delegates_to_llm_client`** — mock `llm_client.structure_report` to return a known string, assert the orchestrator returns it.
2. **`test_structure_report_returns_empty_when_no_llm_client`** — orchestrator built with `llm_client=None`, assert `structure_report` returns `""` and logs a warning.

### Manual smoke test

1. `ollama serve` running, `qwen2.5:3b` pulled.
2. Launch app: `python -m src.main`.
3. Dictate or type a freeform paragraph into the editor, e.g.:
   > "CT chest done today for cough. The lungs are clear. There is a 9mm right upper lobe nodule, new compared to January. Heart normal. No effusion."
4. Click **Structure Report**.
5. Within ~few seconds, the editor contents are replaced with a six-section template. EXAMINATION reads "CT chest.", CLINICAL HISTORY reads "Cough.", TECHNIQUE reads "Not provided", COMPARISON references January, FINDINGS is grouped by anatomic system, IMPRESSION reads "Not provided".
6. **Press Ctrl+Z** — original freeform text is restored (QTextEdit undo). Verify.
7. **Cold-failure path:** stop `ollama serve`, click again. Status reads "Structuring failed". Editor contents unchanged. Log shows the connection-refused hint.
8. **Empty path:** click **Clear**, then click **Structure Report**. Status reads "No text to structure". No LLM call.

## Profiling pass (per project plan template)

Wrap `orchestrator.structure_report` with `LatencyTimer`, mirroring `generate_impression`:

```python
def structure_report(self, text: str) -> str:
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

This makes the cost of generating ~1024 tokens visible in the loguru log so the user can decide whether to switch models if it feels too slow.

## Dead-code / readability pass (per project plan template)

After the new path is proven working end-to-end:

1. Inspect `OllamaClient` for any orphaned imports, commented-out code, or duplicated comments left over from the `_chat` extraction.
2. Verify `_chat` has a tight one-line docstring describing exactly its single responsibility.
3. Check that `generate_impression` and `structure_report` look syntactically parallel (same shape) — that's the signal future LLM features can follow.
4. Confirm no unused widgets or callbacks were added to MainWindow during the wiring pass.
5. Run the full test suite to confirm nothing regressed.

## Implementation order

1. Failing unit tests for `_chat` extraction + `structure_report` (TDD).
2. Refactor `OllamaClient` to extract `_chat`; rewrite `generate_impression` to use it; verify all existing impression tests still pass.
3. Implement `structure_report` on `OllamaClient`; verify new tests pass.
4. Add `structure_report` to `DictationOrchestrator` with profiler timer; add orchestrator unit tests.
5. Add the **Structure Report** button + `on_structure_report` hook in `MainWindow`; verify any existing UI tests still pass.
6. Wire `do_structure_report` in `main.py`; sanity import.
7. Manual smoke test (happy path, undo path, failure paths).
8. Readability pass — confirm `OllamaClient` is tidy, parallel structure between the two methods, no dead code.
9. Final test suite run.
