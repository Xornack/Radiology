# Ollama-backed Impression Generation (POC)

**Date:** 2026-04-23
**Status:** Design approved, ready for implementation plan
**Scope:** Single button (Generate Impression) wired to a local Ollama model

## Goal

Prove the dictation app can call a locally-running Ollama model end-to-end via a single feature: the existing **Generate Impression** button. Today that button POSTs to a hardcoded OpenAI-compatible endpoint (`http://localhost:8001/v1/completions`) that nothing on the user's machine actually serves, so it's a no-op. After this slice it will hit a real local model and return a usable radiology impression. Later phases (other AI features: macros, readback, field templates) reuse the same wiring pattern.

## Non-goals

- LLM registry / UI dropdown for swapping models. Will be a phase-2 follow-up once a second LLM backend exists. Mirrors how the STT registry came after the first STT client.
- Streaming token output. The button is a one-shot — block until the response is ready.
- Multi-turn conversation. One findings-in / impression-out call.
- Model management (pull, list, delete). User runs `ollama pull` outside the app.
- PHI scrubbing changes. Existing `scrub_text` is reused unmodified.

## Architecture

One new module: `src/ai/ollama_client.py`. `main.py` constructs an `OllamaClient` instead of the current `LLMClient` and passes it to the orchestrator. The orchestrator is unchanged because it already calls `self.llm_client.generate_impression(findings)` polymorphically.

The old `LLMClient` is left in place during this slice and deleted in the cleanup pass at the end of the implementation plan.

```
[Generate Impression button]
        |
        v
main.py do_generate_impression()
        |
        v
DictationOrchestrator.generate_impression(findings)
        |
        v
OllamaClient.generate_impression(findings)
        |- scrub_text(findings)
        |- POST /api/chat to Ollama
        |- parse response.message.content
        v
returns str -> main.py appends "IMPRESSION: <text>" to editor
```

## Components

### `OllamaClient` (`src/ai/ollama_client.py`)

```
OllamaClient(url: str, model: str, system_prompt: str | None = None)
    .generate_impression(findings: str) -> str
```

- `url`: full Ollama chat endpoint (default `http://localhost:11434/api/chat`).
- `model`: Ollama model tag (default `qwen2.5:3b`).
- `system_prompt`: optional override. Default is a single sentence:
  > "You are a radiologist's assistant. Given a section of findings, write a concise impression in numbered bullet points. Do not invent findings that are not in the input. Do not include patient identifiers."
- `generate_impression`:
  1. Run `scrub_text(findings)` (PHI scrubber, same module the old client used).
  2. Build payload:
     ```json
     {
       "model": "<model>",
       "messages": [
         {"role": "system", "content": "<system_prompt>"},
         {"role": "user",   "content": "Findings:\n<scrubbed findings>\n\nProvide a concise impression."}
       ],
       "stream": false,
       "options": {"temperature": 0.1}
     }
     ```
  3. `requests.post(url, json=payload, timeout=60)`.
  4. On 200, return `data["message"]["content"].strip()`.
  5. On any failure (timeout, connection refused, non-200, malformed JSON, missing field), log with enough detail to diagnose and return `""`.

The empty-string-on-failure contract matches the existing `LLMClient` so the orchestrator and UI need zero changes — they already render `""` as "Impression failed".

### Settings additions (`src/utils/settings.py`)

- `ollama_url: str` from `OLLAMA_URL`, default `http://localhost:11434/api/chat`.
- `ollama_model: str` from `OLLAMA_MODEL`, default `qwen2.5:3b`.

`llm_url` (the old `LLMClient` setting) stays for now and is removed in the cleanup pass.

### `main.py` swap

Replace:
```python
from src.ai.llm_client import LLMClient
...
llm = LLMClient(url=settings.llm_url)
```
with:
```python
from src.ai.ollama_client import OllamaClient
...
llm = OllamaClient(url=settings.ollama_url, model=settings.ollama_model)
```

No other call sites change.

## Data flow

1. User types or dictates findings into the in-app editor.
2. User clicks **Generate Impression**.
3. `do_generate_impression` (main.py) reads `window.get_findings()`, disables the button, sets status "Generating impression...".
4. Calls `orchestrator.generate_impression(findings)`.
5. Orchestrator delegates to `OllamaClient.generate_impression(findings)`.
6. Client scrubs PHI, POSTs to Ollama, parses, returns a string (or `""`).
7. main.py either appends `IMPRESSION: <text>` to the editor and sets status "Ready", or sets status "Impression failed".

## Error handling

| Failure | Detection | Log | UI |
| --- | --- | --- | --- |
| Ollama not running | `requests.ConnectionError` | warn: "Ollama connection refused at `<url>` — is `ollama serve` running?" | "Impression failed" |
| Slow first call (model load) | `requests.Timeout` after 60s | warn: "Ollama request timed out after 60s (cold model load? consider OLLAMA_KEEP_ALIVE)" | "Impression failed" |
| Model not pulled | HTTP 404 with `{"error":"model ... not found"}` | warn: HTTP status + first 200 chars of body | "Impression failed" |
| Other HTTP error | non-200 | warn: HTTP status + first 200 chars of body | "Impression failed" |
| Malformed response | KeyError / JSONDecodeError | warn with exception type | "Impression failed" |

All paths return `""` from the client. The button stays usable for retry — `do_generate_impression` already re-enables it in a `finally` block.

## Configuration notes for the user

In the user's shell environment (not in app code), recommend:

```
OLLAMA_KEEP_ALIVE=24h
```

so the model stays resident in memory between button clicks. Without this, Ollama unloads after 5 minutes idle and the next click pays a multi-second cold-load tax.

## Testing

### Unit tests (`tests/unit/test_ollama_client.py`)

Mirrors the structure of the existing `tests/unit/test_llm_client.py`:

1. **`test_generate_impression_success`** — mock `requests.post` to return a 200 with `{"message": {"content": "Normal study."}}`. Assert returned string contains expected content.
2. **`test_generate_impression_scrubs_phi`** — patch `scrub_text` to redact a name. Assert the redacted form (not the original) appears in the request payload sent to `requests.post`.
3. **`test_generate_impression_returns_empty_on_connection_error`** — make `requests.post` raise `requests.ConnectionError`. Assert returns `""` (no exception escapes).
4. **`test_generate_impression_returns_empty_on_http_error`** — mock 404 response with `model not found` body. Assert returns `""`.

### Manual smoke test

1. `ollama serve` running.
2. `ollama pull qwen2.5:3b` completed.
3. Launch app: `python -m src.main`.
4. Dictate or type a few sentences of findings into the editor (e.g., "The lungs are clear. The heart is normal in size. No pleural effusion.").
5. Click **Generate Impression**.
6. Within ~few seconds (slower on first click after model load), `IMPRESSION: <text>` appears appended to the editor.
7. Repeat the click — second call should be noticeably faster with `OLLAMA_KEEP_ALIVE` set.
8. Stop `ollama serve`, click again — UI shows "Impression failed", log shows "connection refused" hint.

## Profiling pass (per project plan template)

Wrap the orchestrator call with the existing `LatencyTimer`:

```python
def generate_impression(self, findings: str) -> str:
    if not self.llm_client:
        ...
    if self.profiler:
        self.profiler.start("llm_impression")
    try:
        return self.llm_client.generate_impression(findings)
    finally:
        if self.profiler:
            total = self.profiler.stop("llm_impression")
            logger.info(f"Impression generation: {total:.2f}s")
```

This makes cold-vs-warm Ollama latency visible in the loguru output so the user can decide whether keep-alive tuning is needed.

## Dead-code / readability pass (per project plan template)

After the new path is proven working end-to-end:

1. Delete `src/ai/llm_client.py`.
2. Delete `tests/unit/test_llm_client.py`.
3. Remove `llm_url` from `src/utils/settings.py` and any `LLM_URL` references.
4. Remove the `from src.ai.llm_client import LLMClient` line in `main.py` if not already removed during the swap.
5. Run the full test suite to confirm nothing else referenced the old class.
6. Quick visual pass over `ollama_client.py` and the modified `settings.py` / `main.py` for dead imports, stale comments, or duplicated string constants.

## Implementation order

1. Add `OllamaClient` + unit tests (TDD).
2. Add settings fields.
3. Swap `main.py` constructor.
4. Manual smoke test against running Ollama.
5. Add profiler instrumentation in orchestrator.
6. Run full test suite.
7. Cleanup pass (delete old `LLMClient`, settings, tests, imports).
8. Final test suite run.
