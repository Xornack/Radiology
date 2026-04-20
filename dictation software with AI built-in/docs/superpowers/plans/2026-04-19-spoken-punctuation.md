# Spoken-Punctuation Post-Processor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Whisper's inferred punctuation with user-dictated spoken tokens (PowerScribe-style), with context-aware disambiguation for anatomical `colon`.

**Architecture:** Pure function `apply_punctuation(text) -> str` in `src/engine/punctuation.py`. Called by the orchestrator (after PHI scrub, before keyboard wedge) and by the streaming transcriber (before emitting partials). Internal pipeline: strip Whisper punctuation → tokenize words → map spoken tokens to characters (with colon disambiguation against anatomy word lists) → auto-capitalize → tidy spacing.

**Tech Stack:** Python 3.10+, standard library only (`re`). Tests with `pytest`. Commands run from the project root `C:\Users\harwo\OneDrive\Documents\Radiology\dictation software with AI built-in` using the venv Python: `.venv/Scripts/python.exe -m pytest ...`

---

## File Structure

**Create:**
- `src/engine/punctuation.py` — the pure post-processor.
- `tests/unit/test_punctuation.py` — unit tests.

**Modify:**
- `src/core/orchestrator.py` — insert `apply_punctuation` call after `scrub_text`.
- `src/core/streaming.py` — call `apply_punctuation` in the worker before emitting `partial_ready`.
- `project-plan.md` — add Phase 8.1 entry, remove the "dictated punctuation" item from Known Issues.

---

## Task 1: Module scaffold + empty-input pass-through

**Files:**
- Create: `src/engine/punctuation.py`
- Create: `tests/unit/test_punctuation.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_punctuation.py` with:

```python
from src.engine.punctuation import apply_punctuation


def test_empty_input_returns_empty():
    assert apply_punctuation("") == ""


def test_plain_text_gets_capitalized():
    # No Whisper punctuation, no spoken tokens → just capitalize first letter
    assert apply_punctuation("the lungs are clear") == "The lungs are clear"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_punctuation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.engine.punctuation'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/engine/punctuation.py`:

```python
import re


def apply_punctuation(text: str) -> str:
    """
    PowerScribe-style post-processor. Strips Whisper's auto-punctuation and
    replaces dictated tokens (period, comma, new paragraph, colon, ...) with
    the matching characters. Pure function; safe to call on live partials.
    """
    if not text:
        return text
    # Capitalize first lowercase alpha at start of text.
    return re.sub(r"^(\s*)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_punctuation.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/engine/punctuation.py tests/unit/test_punctuation.py
git commit -m "Add punctuation module scaffold with pass-through behavior"
```

---

## Task 2: Strip Whisper auto-punctuation (preserve decimals)

**Files:**
- Modify: `src/engine/punctuation.py`
- Modify: `tests/unit/test_punctuation.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_punctuation.py`:

```python
def test_strips_whisper_commas():
    # No spoken "comma" token → Whisper's comma must be removed.
    assert apply_punctuation("the lungs, are clear") == "The lungs are clear"


def test_strips_whisper_periods():
    assert apply_punctuation("lungs clear. heart normal") == "Lungs clear heart normal"


def test_strips_whisper_question_and_exclamation():
    assert apply_punctuation("is it clear? yes!") == "Is it clear yes"


def test_strips_whisper_colon_and_semicolon():
    assert apply_punctuation("findings: clear; no masses") == "Findings clear no masses"


def test_preserves_decimals():
    assert apply_punctuation("the mass measures 7.5 mm") == "The mass measures 7.5 mm"


def test_preserves_apostrophes_in_contractions():
    assert apply_punctuation("it's normal") == "It's normal"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_punctuation.py -v`
Expected: the six new tests FAIL (commas/periods/etc. still present in output).

- [ ] **Step 3: Add the strip step**

Replace the body of `apply_punctuation` in `src/engine/punctuation.py`:

```python
import re


_DOT_STRIP_RE = re.compile(r"(?<!\d)\.(?!\d)")
_OTHER_STRIP_RE = re.compile(r"[,?!;:]")


def _strip_whisper_punctuation(text: str) -> str:
    """Remove Whisper-inferred punctuation. Preserves decimals and apostrophes."""
    text = _DOT_STRIP_RE.sub("", text)
    text = _OTHER_STRIP_RE.sub("", text)
    return text


def _autocap_first_letter(text: str) -> str:
    return re.sub(
        r"^(\s*)([a-z])",
        lambda m: m.group(1) + m.group(2).upper(),
        text,
    )


def apply_punctuation(text: str) -> str:
    """
    PowerScribe-style post-processor. Strips Whisper's auto-punctuation and
    replaces dictated tokens (period, comma, new paragraph, colon, ...) with
    the matching characters. Pure function; safe to call on live partials.
    """
    if not text:
        return text
    text = _strip_whisper_punctuation(text)
    # Collapse runs of spaces left behind by strip.
    text = re.sub(r"[ \t]+", " ", text).strip()
    text = _autocap_first_letter(text)
    return text
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_punctuation.py -v`
Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/engine/punctuation.py tests/unit/test_punctuation.py
git commit -m "Strip Whisper auto-punctuation, preserving decimals and apostrophes"
```

---

## Task 3: Single-word token substitutions

**Files:**
- Modify: `src/engine/punctuation.py`
- Modify: `tests/unit/test_punctuation.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_punctuation.py`:

```python
def test_token_period():
    assert apply_punctuation("lungs clear period") == "Lungs clear."


def test_token_comma():
    assert apply_punctuation("lungs comma heart comma kidneys") == "Lungs, heart, kidneys"


def test_token_semicolon():
    assert apply_punctuation("lungs clear semicolon heart normal") == "Lungs clear; heart normal"


def test_token_semicolon_hyphenated_variant():
    # Whisper sometimes emits "semi-colon" as a single token with a hyphen.
    assert apply_punctuation("lungs clear semi-colon heart normal") == "Lungs clear; heart normal"


def test_token_hyphen():
    assert apply_punctuation("follow up hyphen imaging") == "Follow up - imaging"


def test_token_dash():
    assert apply_punctuation("finding dash incidental") == "Finding — incidental"
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_punctuation.py -v`
Expected: the six new tests FAIL (spoken tokens still appear literally).

- [ ] **Step 3: Implement single-word substitution**

In `src/engine/punctuation.py`, add above `apply_punctuation`:

```python
_SINGLE_WORD_MAP = {
    "period": ".",
    "comma": ",",
    "semicolon": ";",
    "semi-colon": ";",
    "hyphen": "-",
    "dash": " \u2014 ",    # em-dash with surrounding spaces
}
```

Then replace the body of `apply_punctuation` with:

```python
def apply_punctuation(text: str) -> str:
    if not text:
        return text
    text = _strip_whisper_punctuation(text)
    text = _substitute_tokens(text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    text = _autocap_first_letter(text)
    return text
```

And add the helper:

```python
def _substitute_tokens(text: str) -> str:
    """Word-by-word replacement of spoken tokens with their characters."""
    words = text.split()
    output: list[str] = []
    for w in words:
        key = w.lower()
        if key in _SINGLE_WORD_MAP:
            output.append(_SINGLE_WORD_MAP[key])
        else:
            output.append(w)
    joined = " ".join(output)
    # Tighten: strip space before closing punctuation.
    joined = re.sub(r"\s+([.,!?;:)])", r"\1", joined)
    return joined
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_punctuation.py -v`
Expected: all 14 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/engine/punctuation.py tests/unit/test_punctuation.py
git commit -m "Map single-word punctuation tokens (period, comma, semicolon, hyphen, dash)"
```

---

## Task 4: Multi-word token substitutions

**Files:**
- Modify: `src/engine/punctuation.py`
- Modify: `tests/unit/test_punctuation.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_punctuation.py`:

```python
def test_token_question_mark():
    assert apply_punctuation("is it clear question mark") == "Is it clear?"


def test_token_exclamation_point():
    assert apply_punctuation("ouch exclamation point") == "Ouch!"


def test_token_exclamation_mark_variant():
    assert apply_punctuation("ouch exclamation mark") == "Ouch!"


def test_token_new_paragraph():
    assert apply_punctuation("first line new paragraph second line") == "First line\n\nsecond line"


def test_token_next_paragraph_variant():
    assert apply_punctuation("first line next paragraph second line") == "First line\n\nsecond line"


def test_token_new_line():
    assert apply_punctuation("line one new line line two") == "Line one\nline two"


def test_token_parentheses():
    assert apply_punctuation(
        "incidental finding open paren likely benign close paren"
    ) == "Incidental finding (likely benign)"


def test_token_open_parenthesis_variant():
    assert apply_punctuation(
        "incidental finding open parenthesis likely benign close parenthesis"
    ) == "Incidental finding (likely benign)"


def test_token_quotes():
    assert apply_punctuation(
        'open quote normal close quote study'
    ) == '"normal" study'


def test_chained_period_and_new_paragraph():
    assert (
        apply_punctuation("sentence one period new paragraph sentence two period")
        == "Sentence one.\n\nsentence two."
    )
```

Note: auto-capitalization after `.` / `\n\n` lands in Task 6, so `sentence two` is lowercase here on purpose. Update in Task 6.

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_punctuation.py -v`
Expected: the 10 new tests FAIL.

- [ ] **Step 3: Add the multi-word map**

In `src/engine/punctuation.py`, add above `_SINGLE_WORD_MAP`:

```python
_MULTI_WORD_MAP = {
    "question mark": "?",
    "exclamation point": "!",
    "exclamation mark": "!",
    "new paragraph": "\n\n",
    "next paragraph": "\n\n",
    "new line": "\n",
    "open paren": "(",
    "open parenthesis": "(",
    "close paren": ")",
    "close parenthesis": ")",
    "open quote": '"',
    "close quote": '"',
}
```

Replace `_substitute_tokens` with:

```python
def _substitute_tokens(text: str) -> str:
    """Replace multi-word and single-word spoken tokens with their characters."""
    words = text.split()
    output: list[str] = []
    i = 0
    while i < len(words):
        if i + 1 < len(words):
            pair = f"{words[i].lower()} {words[i + 1].lower()}"
            if pair in _MULTI_WORD_MAP:
                output.append(_MULTI_WORD_MAP[pair])
                i += 2
                continue
        key = words[i].lower()
        if key in _SINGLE_WORD_MAP:
            output.append(_SINGLE_WORD_MAP[key])
        else:
            output.append(words[i])
        i += 1
    joined = " ".join(output)
    # Tighten: strip whitespace before closing punctuation; after opening paren.
    joined = re.sub(r"\s+([.,!?;:)])", r"\1", joined)
    joined = re.sub(r"\(\s+", "(", joined)
    return joined
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_punctuation.py -v`
Expected: all 24 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/engine/punctuation.py tests/unit/test_punctuation.py
git commit -m "Map multi-word punctuation tokens (question mark, new paragraph, parens, quotes)"
```

---

## Task 5: Colon with anatomy disambiguation

**Files:**
- Modify: `src/engine/punctuation.py`
- Modify: `tests/unit/test_punctuation.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_punctuation.py`:

```python
def test_colon_as_punctuation():
    assert apply_punctuation("findings colon one mass") == "Findings: one mass"


def test_colon_anatomy_preceded_by_distal():
    assert apply_punctuation("fluid in the distal colon") == "Fluid in the distal colon"


def test_colon_anatomy_preceded_by_sigmoid():
    assert apply_punctuation("mass in the sigmoid colon") == "Mass in the sigmoid colon"


def test_colon_anatomy_followed_by_cancer():
    assert apply_punctuation("colon cancer screening") == "Colon cancer screening"


def test_colon_anatomy_followed_by_polyp():
    assert apply_punctuation("the colon polyp was removed") == "The colon polyp was removed"


def test_colon_at_start_not_anatomy_becomes_punctuation():
    # First word "colon" with no anatomy neighbor before or after.
    assert apply_punctuation("colon finding") == ": finding"
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_punctuation.py -v`
Expected: the six new tests FAIL (either all "colon" become `:`, or all stay as `colon`).

- [ ] **Step 3: Implement colon disambiguation**

In `src/engine/punctuation.py`, add above `_SINGLE_WORD_MAP`:

```python
_COLON_ANATOMY_BEFORE = {
    "transverse", "sigmoid", "ascending", "descending",
    "distal", "proximal", "hepatic", "splenic",
    "rectosigmoid", "right", "left", "entire", "intra",
}

_COLON_ANATOMY_AFTER = {
    "cancer", "polyp", "polyps", "mass", "wall", "lumen",
    "mucosa", "stricture", "diverticulosis", "diverticulitis",
    "stenosis", "obstruction", "perforation", "resection",
    "carcinoma", "neoplasm", "tumor", "tumour", "lesion", "lesions",
}
```

Replace the inside of the `while i < len(words)` loop in `_substitute_tokens` so that before the single-word check, it handles `colon` specifically. The full replacement for the loop body:

```python
    while i < len(words):
        if i + 1 < len(words):
            pair = f"{words[i].lower()} {words[i + 1].lower()}"
            if pair in _MULTI_WORD_MAP:
                output.append(_MULTI_WORD_MAP[pair])
                i += 2
                continue
        key = words[i].lower()
        if key == "colon":
            prev_word = words[i - 1].lower() if i > 0 else ""
            next_word = words[i + 1].lower() if i + 1 < len(words) else ""
            if prev_word in _COLON_ANATOMY_BEFORE or next_word in _COLON_ANATOMY_AFTER:
                output.append(words[i])   # preserve anatomical word
            else:
                output.append(":")
            i += 1
            continue
        if key in _SINGLE_WORD_MAP:
            output.append(_SINGLE_WORD_MAP[key])
        else:
            output.append(words[i])
        i += 1
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_punctuation.py -v`
Expected: all 30 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/engine/punctuation.py tests/unit/test_punctuation.py
git commit -m "Add context-aware colon disambiguation using anatomy word lists"
```

---

## Task 6: Auto-capitalization after sentence-enders

**Files:**
- Modify: `src/engine/punctuation.py`
- Modify: `tests/unit/test_punctuation.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_punctuation.py`:

```python
def test_autocap_after_period():
    assert (
        apply_punctuation("first sentence period second sentence period")
        == "First sentence. Second sentence."
    )


def test_autocap_after_new_paragraph():
    assert (
        apply_punctuation("sentence one period new paragraph sentence two period")
        == "Sentence one.\n\nSentence two."
    )


def test_autocap_after_question_mark():
    assert (
        apply_punctuation("is it clear question mark yes period")
        == "Is it clear? Yes."
    )


def test_autocap_after_exclamation():
    assert (
        apply_punctuation("great exclamation point more to come period")
        == "Great! More to come."
    )
```

The `test_chained_period_and_new_paragraph` test from Task 4 expects `sentence two` lowercase — update it now to expect `Sentence two` capitalized:

Replace the existing assertion in `test_chained_period_and_new_paragraph` with:

```python
    assert (
        apply_punctuation("sentence one period new paragraph sentence two period")
        == "Sentence one.\n\nSentence two."
    )
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_punctuation.py -v`
Expected: the 4 new tests FAIL, and `test_chained_period_and_new_paragraph` now also fails.

- [ ] **Step 3: Implement broader auto-cap**

Replace `_autocap_first_letter` in `src/engine/punctuation.py` with:

```python
def _autocap(text: str) -> str:
    """Capitalize first alpha of document, and first alpha after ., ?, !, or blank line."""
    # First alpha of the text (after optional leading whitespace).
    text = re.sub(
        r"^(\s*)([a-z])",
        lambda m: m.group(1) + m.group(2).upper(),
        text,
    )
    # First alpha after a sentence-ending punctuation + whitespace.
    text = re.sub(
        r"([.!?]\s+)([a-z])",
        lambda m: m.group(1) + m.group(2).upper(),
        text,
    )
    # First alpha after a paragraph break.
    text = re.sub(
        r"(\n\n+)([a-z])",
        lambda m: m.group(1) + m.group(2).upper(),
        text,
    )
    return text
```

And update the call in `apply_punctuation`:

```python
def apply_punctuation(text: str) -> str:
    if not text:
        return text
    text = _strip_whisper_punctuation(text)
    text = _substitute_tokens(text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    text = _autocap(text)
    return text
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_punctuation.py -v`
Expected: all 34 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/engine/punctuation.py tests/unit/test_punctuation.py
git commit -m "Auto-capitalize first word of document and after sentence enders"
```

---

## Task 7: Spacing hygiene (collapse spaces, line-trim, paragraph collapse)

**Files:**
- Modify: `src/engine/punctuation.py`
- Modify: `tests/unit/test_punctuation.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_punctuation.py`:

```python
def test_collapses_interior_whitespace():
    assert apply_punctuation("hello    world   period") == "Hello world."


def test_strips_leading_whitespace_per_line():
    # After "new paragraph", Whisper might have leading space on the next chunk.
    assert (
        apply_punctuation("one period new paragraph    two period")
        == "One.\n\nTwo."
    )


def test_no_space_before_punctuation():
    assert apply_punctuation("word  comma  word  period") == "Word, word."


def test_collapses_triple_newlines():
    # Two "new paragraph" tokens in a row collapse to a single paragraph break.
    assert (
        apply_punctuation("one new paragraph new paragraph two")
        == "One\n\ntwo"
    )
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_punctuation.py -v`
Expected: the 4 new tests FAIL (extra spaces remain, leading line whitespace remains, triple newlines remain).

- [ ] **Step 3: Add a dedicated tidy step**

Add this helper to `src/engine/punctuation.py`:

```python
def _tidy_spacing(text: str) -> str:
    # Collapse runs of space/tab (but not newlines).
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse 3+ newlines into exactly two.
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip whitespace at start/end of each line.
    text = "\n".join(line.strip() for line in text.split("\n"))
    return text.strip()
```

Replace the body of `apply_punctuation`:

```python
def apply_punctuation(text: str) -> str:
    if not text:
        return text
    text = _strip_whisper_punctuation(text)
    text = _substitute_tokens(text)
    text = _tidy_spacing(text)
    text = _autocap(text)
    return text
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_punctuation.py -v`
Expected: all 38 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/engine/punctuation.py tests/unit/test_punctuation.py
git commit -m "Tidy whitespace: collapse spaces, trim lines, cap paragraph breaks"
```

---

## Task 8: End-to-end acceptance test

**Files:**
- Modify: `tests/unit/test_punctuation.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_punctuation.py`:

```python
def test_acceptance_full_dictation():
    """
    Full PowerScribe-style dictation from the spec's acceptance criteria.
    Exercises: period, new paragraph, colon (punctuation, not anatomy),
    auto-capitalization after periods and paragraph breaks, preservation
    of hyphenated 'x-ray'.
    """
    dictated = (
        "the lungs are clear period no acute findings period "
        "new paragraph impression colon normal chest x-ray period"
    )
    expected = (
        "The lungs are clear. No acute findings.\n\n"
        "Impression: normal chest x-ray."
    )
    assert apply_punctuation(dictated) == expected


def test_acceptance_decimal_measurement():
    """Decimals survive the strip phase and are not split by tokens."""
    dictated = "the mass measures 7.5 mm period"
    assert apply_punctuation(dictated) == "The mass measures 7.5 mm."


def test_acceptance_colon_mixed_usage():
    """Colon used both as anatomy and as punctuation in one report."""
    dictated = (
        "findings colon fluid in the distal colon period "
        "new paragraph impression colon colitis period"
    )
    expected = (
        "Findings: fluid in the distal colon.\n\n"
        "Impression: colitis."
    )
    assert apply_punctuation(dictated) == expected
```

- [ ] **Step 2: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_punctuation.py -v`
Expected: all 41 tests PASS (these were designed to exercise already-implemented behavior; if any fail, the fix is in the earlier tasks, not here).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_punctuation.py
git commit -m "Add end-to-end acceptance tests for punctuation post-processor"
```

---

## Task 9: Wire `apply_punctuation` into the orchestrator

**Files:**
- Modify: `src/core/orchestrator.py`
- Modify: `tests/integration/test_orchestrator.py`

- [ ] **Step 1: Update the orchestrator test to exercise the punctuation pass**

In `tests/integration/test_orchestrator.py`, modify `test_full_dictation_pipeline_logic`. Change **only** the mock whisper return value so Whisper emits the spoken `period` token instead of a `.`. The final assertion is unchanged — that's the point: the wedge still receives `"Patient [NAME]."` because `apply_punctuation` converts the spoken token.

Replace:

```python
    mock_whisper.transcribe.return_value = "Patient John Doe."
```

with:

```python
    mock_whisper.transcribe.return_value = "Patient John Doe period"
```

Leave the final `mock_wedge.type_text.assert_called_with("Patient [NAME].")` assertion exactly as it is.

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_orchestrator.py -v`
Expected: `test_full_dictation_pipeline_logic` FAILS. The wedge receives `"Patient [NAME] period"` because `apply_punctuation` is not yet called.

- [ ] **Step 3: Wire `apply_punctuation` into the orchestrator**

Edit `src/core/orchestrator.py`. Add this import near the top:

```python
from src.engine.punctuation import apply_punctuation
```

Then in `handle_trigger_up`, between the scrub step and the wedge step, insert the punctuation pass. The updated section looks like:

```python
        # 3. Scrub PHI
        clean_text = scrub_text(raw_text)

        # 3b. Apply spoken-punctuation post-processor.
        clean_text = apply_punctuation(clean_text)

        if self.profiler:
            self.profiler.stop("scrubbing")
            self.profiler.start("keyboard_wedge")
```

- [ ] **Step 4: Run the integration tests**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_orchestrator.py -v`
Expected: all orchestrator tests PASS.

- [ ] **Step 5: Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: all prior tests still PASS (52+ tests counting the new punctuation tests).

- [ ] **Step 6: Commit**

```bash
git add src/core/orchestrator.py tests/integration/test_orchestrator.py
git commit -m "Wire apply_punctuation into orchestrator after PHI scrub"
```

---

## Task 10: Wire `apply_punctuation` into the streaming transcriber

**Files:**
- Modify: `src/core/streaming.py`

- [ ] **Step 1: Add the import**

At the top of `src/core/streaming.py`, add:

```python
from src.engine.punctuation import apply_punctuation
```

- [ ] **Step 2: Apply punctuation before emitting partials**

In `_transcribe_worker`, replace:

```python
            text = self.whisper_client.transcribe(wav_bytes)
            if self._active and text:
                self.partial_ready.emit(text)
```

with:

```python
            text = self.whisper_client.transcribe(wav_bytes)
            if self._active and text:
                self.partial_ready.emit(apply_punctuation(text))
```

- [ ] **Step 3: Run the full suite to confirm nothing regresses**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add src/core/streaming.py
git commit -m "Apply punctuation post-processor to streaming partials"
```

---

## Task 11: Update project-plan.md and final sweep

**Files:**
- Modify: `project-plan.md`

- [ ] **Step 1: Add Phase 8 entry**

At the end of `project-plan.md`, BEFORE the `## Known Issues & Next Steps` section, insert:

```markdown
---

## Phase 8: Dictation UX

### Task 8.1: Spoken Punctuation Post-Processor ✅
**Added:** `src/engine/punctuation.py` replaces Whisper's inferred punctuation
with user-dictated tokens (PowerScribe-style). Handles `period`, `comma`,
`question mark`, `exclamation point`, `colon`, `semicolon`, `new paragraph`,
`new line`, parentheses, quotes, `hyphen`, and `dash`. Context-aware colon
disambiguation: preserves `colon` as anatomy when neighbored by words like
`distal`, `sigmoid`, `cancer`, `polyp`. Auto-capitalizes document start and
first word after `.`, `?`, `!`, or a paragraph break. Called after PHI scrub
in the orchestrator and before `partial_ready.emit` in the streaming
transcriber so the UI preview matches the final output.
```

- [ ] **Step 2: Remove stale "dictated punctuation" bullet**

In the `## Known Issues & Next Steps` section of `project-plan.md`, delete this bullet:

```markdown
- **Dictated punctuation** — Whisper's own inferred punctuation is imperfect
  for clinical speech, and spoken commands ("comma", "period", "new paragraph")
  are not recognized. Needs a post-processor that maps spoken tokens to
  punctuation characters. *[Deferred]*
```

- [ ] **Step 3: Run the full test suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add project-plan.md
git commit -m "Project plan: mark Phase 8.1 spoken-punctuation done"
```

---

## Verification Summary

After all tasks, the engineer should be able to:

1. Run `.venv/Scripts/python.exe -m pytest tests/ -q` and see all tests pass.
2. Launch `python -m src.main`, dictate the acceptance phrase
   *"the lungs are clear period no acute findings period new paragraph impression colon normal chest x-ray period"*,
   and see the wedge output
   `"The lungs are clear. No acute findings.\n\nImpression: normal chest x-ray."`
3. Dictate *"fluid in the distal colon period"* and see `colon` preserved
   as anatomy, with the sentence ending on a period.
