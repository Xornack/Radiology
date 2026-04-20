# Spoken-Punctuation Post-Processor — Design

**Date:** 2026-04-19
**Author:** Matthew Harwood, MD (w/ Claude)
**Status:** Approved; implementation pending

## Goal

Give the radiology dictation platform PowerScribe-style explicit punctuation
control: the radiologist dictates every comma, period, and "new paragraph" by
voice, and those spoken tokens are converted to the matching characters
before the text is typed into the target application. Whisper's own inferred
punctuation is suppressed so the user is the sole source of punctuation.

## Non-Goals

- Capitalization commands (`cap`, `all caps`).
- Meta commands (`scratch that`, `undo`).
- User-trainable vocabulary or per-user customization.
- Disambiguation for words beyond `colon`.

These are candidates for a v2 pass; the module is structured so they can be
added without breaking callers.

## Module

`src/engine/punctuation.py` exposing a single pure function:

```python
def apply_punctuation(text: str) -> str: ...
```

No state, no I/O, no logger writes in the happy path. All lookup tables are
module-level constants so future configurability can swap them out.

## Pipeline Placement

1. `DictationOrchestrator.handle_trigger_up` calls `apply_punctuation` after
   `scrub_text` and before `wedge.type_text`. Scrubbing runs first because
   PHI regexes are tolerant of Whisper's noisy punctuation; the punctuation
   pass is purely a text-formatting step.
2. `StreamingTranscriber._transcribe_worker` calls `apply_punctuation` on
   partial text before emitting `partial_ready`, so the UI shows the same
   cleaned form during dictation as after commit.

## Processing Order (inside `apply_punctuation`)

1. **Strip Whisper auto-punctuation.** Remove `, . ? ! : ;` except:
   - Decimals (`\d\.\d`) — keep the dot.
   - Mid-word hyphens — keep.
   - Apostrophes in contractions — keep (not in the strip set anyway).
2. **Token substitution** (case-insensitive, word-boundary matched):
   - `period` → `.`
   - `comma` → `,`
   - `question mark` → `?`
   - `exclamation point` / `exclamation mark` → `!`
   - `semicolon` / `semi-colon` → `;`
   - `colon` → `:` *(subject to disambiguation rule, step 3)*
   - `new paragraph` / `next paragraph` → `\n\n`
   - `new line` → `\n`
   - `open paren` / `open parenthesis` → `(`
   - `close paren` / `close parenthesis` → `)`
   - `open quote` → `"`
   - `close quote` → `"`
   - `hyphen` → `-`
   - `dash` → ` — ` (em-dash with surrounding spaces)
3. **Colon disambiguation.** Before replacing `colon` with `:`, check both
   immediate neighbors. If either is in the anatomy list, leave `colon` as
   the literal word.
   - Preceding-word anatomy set: `transverse, sigmoid, ascending, descending,
     distal, proximal, hepatic, splenic, rectosigmoid, right, left, entire,
     intra`
   - Following-word anatomy set: `cancer, polyp, mass, wall, lumen, mucosa,
     stricture, diverticulosis, diverticulitis, stenosis, obstruction,
     perforation, resection, carcinoma, neoplasm, tumor, lesion`
4. **Auto-capitalize** the first alphabetic character of the document and the
   first alphabetic character after `.`, `?`, `!`, or a blank line.
5. **Tighten spacing.** Collapse runs of spaces to one; strip whitespace
   before `. , ? ! : ; )`; strip whitespace after `(`; strip trailing
   whitespace on each line; collapse 3+ newlines to exactly two.

## Testing Strategy (TDD)

Tests live in `tests/unit/test_punctuation.py`. One test per rule, each
written RED before the implementation. Coverage:

- Single-token mapping for every entry in the token map.
- Multi-token chains: `"period new paragraph"` → `".\n\n"`.
- Colon punctuation: `"findings colon one mass"` → `"Findings: one mass"`.
- Colon anatomy: `"fluid in the distal colon"` → preserves the word `colon`.
- Colon anatomy follow-word: `"colon cancer screening"` → preserves `colon`.
- Decimals preserved: `"seven point five mm"` stays intact; `"7.5 mm"` stays
  intact through the strip phase.
- Contractions preserved: `"it's normal"` stays `"it's normal"`.
- Whisper commas stripped: `"the lungs, are clear"` → `"the lungs are clear"`
  (no spoken comma token, so comma should not survive).
- Auto-capitalization: first word capitalized; post-period word capitalized;
  post-paragraph word capitalized.
- Spacing hygiene: `"hello  ,  world"` → `"hello, world"`.
- Empty input: `""` → `""`.
- No-op input (already clean, no punctuation tokens): passes through with
  only leading-capital applied.

## Out-of-Scope Behavior Confirmed

- `"colon"` at clause boundary with anatomy-context word beyond ±1 still
  maps to `:`. Documented limitation; the simple rule handles the
  overwhelming-majority case.
- Dictated numerals (e.g. `"three point five"` → `"3.5"`) are a separate
  feature — not in this pass.
- `cap`, `all caps`, `scratch that` are deferred. Auto-capitalization covers
  the most common need.

## Risks & Mitigations

- **Whisper transcribing `"period"` as `"a period"` or `"appeared"`.**
  Nothing we can do purely in post; acceptable baseline. User will notice
  and re-dictate. Mitigation available in v2 via a fuzzier matcher or a
  confidence-scored LLM pass.
- **Colon disambiguation false negatives/positives.** The rule is
  intentionally conservative. False negatives (anatomy treated as `:`)
  produce obvious nonsense the user will catch. False positives (`:`
  treated as anatomy) leave the literal word `colon` in the output — also
  obvious. Both are correctable by the user in a second pass.
- **Performance on streaming partials.** `apply_punctuation` is pure-Python
  regex + string ops on already-short Whisper output; cost is negligible
  relative to the STT itself.

## Files Touched

Add:
- `src/engine/punctuation.py`
- `tests/unit/test_punctuation.py`

Modify:
- `src/core/orchestrator.py` — call `apply_punctuation` after `scrub_text`.
- `src/core/streaming.py` — call `apply_punctuation` in the worker before
  emitting `partial_ready`.
- `project-plan.md` — add Phase 8.1 entry; remove the "dictated punctuation"
  item from Known Issues.

## Acceptance Criteria

- All existing tests continue to pass.
- New test file covers every bullet in "Testing Strategy".
- End-to-end manual check: dictating `"the lungs are clear period no acute
  findings period new paragraph impression colon normal chest x-ray period"`
  produces `"The lungs are clear. No acute findings.\n\nImpression: normal
  chest x-ray."` at the wedge output.
