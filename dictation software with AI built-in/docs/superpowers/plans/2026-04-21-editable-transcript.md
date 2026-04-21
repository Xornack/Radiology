# Editable Transcript + Insert-at-Cursor Dictation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the in-app transcript an editable document that accepts dictation at the current cursor position, and add an In-app / Wedge mode toggle so the same app can dictate either into its own editor or into any focused external window via the existing keyboard wedge.

**Architecture:** Three existing files carry the change. `MainWindow` removes `setReadOnly(True)`, adds a `QTextCharFormat` for dictated text, reworks `begin_streaming` / `update_partial` / `commit_partial` to anchor at the current cursor position (with a `_partial_len` bookkeeping integer), consolidates Record/Stop into a single toggle, adds a `QComboBox` mode toggle, and docks a `QSizeGrip` in the bottom-right. `DictationOrchestrator.handle_trigger_up` grows a `mode: str = "inapp"` parameter that gates whether the keyboard wedge is called. `main.py` reads the mode on Stop and passes it through; in Wedge mode it keeps streaming stopped and appends finalized utterances to the editor as a read-only history.

**Tech Stack:** PyQt6 (`QTextEdit`, `QTextCursor`, `QTextCharFormat`, `QComboBox`, `QSizeGrip`), existing `StreamingTranscriber`, `DictationOrchestrator`, `utils/profiler.py` (`LatencyTimer`), `pytest` + `pytest-qt`.

**Reference spec:** `docs/superpowers/specs/2026-04-21-editable-transcript-design.md`

---

## Task 1: Orchestrator accepts a `mode` parameter (TDD)

**Why:** Decouples the dictation pipeline's final sink from its internals so the UI can choose between "land in in-app editor" (In-app) and "type into externally focused window" (Wedge). Back-compat: `mode="inapp"` is the new default, but the existing integration test will be updated to pass `mode="wedge"` explicitly since that is the behavior it asserts.

**Files:**
- Modify: `src/core/orchestrator.py`
- Create: `tests/unit/test_orchestrator.py`
- Modify: `tests/integration/test_orchestrator.py`

- [ ] **Step 1.1: Write failing unit tests for `handle_trigger_up(mode=...)`**

Create `tests/unit/test_orchestrator.py`:

```python
from unittest.mock import MagicMock, patch
from src.core.orchestrator import DictationOrchestrator


def _make_orch(transcription: str = "hello world"):
    mock_recorder = MagicMock()
    mock_recorder.get_wav_bytes.return_value = b"wav"
    mock_whisper = MagicMock()
    mock_whisper.transcribe.return_value = transcription
    mock_wedge = MagicMock()
    return DictationOrchestrator(
        recorder=mock_recorder,
        whisper_client=mock_whisper,
        wedge=mock_wedge,
    )


def test_handle_trigger_up_inapp_mode_does_not_call_wedge():
    """In-app mode routes text only to the caller, never to the wedge."""
    orch = _make_orch("Findings comma normal period")
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        result = orch.handle_trigger_up(mode="inapp")
    assert result == "Findings, normal."
    orch.wedge.type_text.assert_not_called()


def test_handle_trigger_up_wedge_mode_calls_wedge_and_returns_text():
    """Wedge mode sends text via SendInput AND returns it for history display."""
    orch = _make_orch("Chest clear period")
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        result = orch.handle_trigger_up(mode="wedge")
    assert result == "Chest clear."
    orch.wedge.type_text.assert_called_once_with("Chest clear.")


def test_handle_trigger_up_wedge_mode_empty_text_skips_wedge():
    """Empty transcriptions must not be injected externally."""
    orch = _make_orch("")
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        result = orch.handle_trigger_up(mode="wedge")
    assert result == ""
    orch.wedge.type_text.assert_not_called()


def test_handle_trigger_up_defaults_to_inapp_mode():
    """Default mode must be 'inapp' so new callers don't accidentally emit keystrokes."""
    orch = _make_orch("hello")
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        orch.handle_trigger_up()
    orch.wedge.type_text.assert_not_called()
```

- [ ] **Step 1.2: Run the new tests to verify they fail**

Run: `python -m pytest tests/unit/test_orchestrator.py -v`
Expected: 4 failures — `TypeError: handle_trigger_up() got an unexpected keyword argument 'mode'` (or the default-mode test fails because the wedge is called today).

- [ ] **Step 1.3: Implement the `mode` parameter in `handle_trigger_up`**

Edit `src/core/orchestrator.py`. Replace the `handle_trigger_up` method with:

```python
    def handle_trigger_up(self, mode: str = "inapp") -> str:
        """
        Process the recording and return the finalized text.

        `mode` selects the output sink:
          - "inapp":  text lands in the caller's UI editor (no external keystrokes).
          - "wedge":  text is also typed into the externally focused window via SendInput.
        The returned text is the same in both modes so the caller can display history.
        """
        logger.info("Dictation stopped. Processing...")
        self.recorder.stop()
        if self.profiler:
            self.profiler.stop("audio_capture")
            self.profiler.start("whisper_stt")

        audio_bytes = self.recorder.get_wav_bytes()
        raw_text = self.whisper_client.transcribe(audio_bytes)
        if self.profiler:
            self.profiler.stop("whisper_stt")
            self.profiler.start("scrubbing")

        clean_text = scrub_text(raw_text)
        clean_text = apply_punctuation(clean_text)

        if self.profiler:
            self.profiler.stop("scrubbing")
            self.profiler.start("keyboard_wedge")

        if mode == "wedge" and clean_text:
            try:
                self.wedge.type_text(clean_text)
            except Exception as e:
                logger.error(f"Keyboard wedge failed: {e}")

        if self.profiler:
            self.profiler.stop("keyboard_wedge")
            total = self.profiler.stop("full_pipeline")
            logger.info(f"Pipeline complete. Total latency: {total:.4f}s")

        return clean_text
```

- [ ] **Step 1.4: Update the existing integration test to pass `mode="wedge"` explicitly**

Edit `tests/integration/test_orchestrator.py`. Change line 31 from:

```python
        orch.handle_trigger_up()
```

to:

```python
        orch.handle_trigger_up(mode="wedge")
```

- [ ] **Step 1.5: Run all orchestrator tests**

Run: `python -m pytest tests/unit/test_orchestrator.py tests/integration/test_orchestrator.py -v`
Expected: all 7 tests pass (4 new unit + 3 existing integration).

- [ ] **Step 1.6: Commit**

```bash
git add src/core/orchestrator.py tests/unit/test_orchestrator.py tests/integration/test_orchestrator.py
git commit -m "Orchestrator: mode param gates keyboard wedge (inapp default, wedge opt-in)"
```

---

## Task 2: MainWindow editor becomes editable

**Why:** Removes the read-only barrier so the transcript accepts mouse/keyboard edits. This is a one-line production change but a test asserts the new contract so we can't silently regress it.

**Files:**
- Modify: `src/ui/main_window.py:99-102`
- Modify: `tests/unit/test_main_window.py`

- [ ] **Step 2.1: Write the failing test**

Append to `tests/unit/test_main_window.py`:

```python
def test_editor_is_editable_on_construction(qtbot):
    """The transcript editor must accept user input by default (In-app mode)."""
    window = MainWindow()
    qtbot.addWidget(window)
    assert not window.editor.isReadOnly()
```

- [ ] **Step 2.2: Run the test to verify it fails**

Run: `python -m pytest tests/unit/test_main_window.py::test_editor_is_editable_on_construction -v`
Expected: FAIL (`isReadOnly()` returns True today).

- [ ] **Step 2.3: Remove `setReadOnly(True)`**

Edit `src/ui/main_window.py`. At approximately line 100, change:

```python
        self.editor = QTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setPlaceholderText("Dictation transcript appears here...")
```

to:

```python
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Dictation transcript appears here...")
```

- [ ] **Step 2.4: Run the test to verify it passes**

Run: `python -m pytest tests/unit/test_main_window.py::test_editor_is_editable_on_construction -v`
Expected: PASS.

- [ ] **Step 2.5: Run the full window test file for regressions**

Run: `python -m pytest tests/unit/test_main_window.py -v`
Expected: all tests pass.

- [ ] **Step 2.6: Commit**

```bash
git add src/ui/main_window.py tests/unit/test_main_window.py
git commit -m "MainWindow: transcript editor is editable by default"
```

---

## Task 3: Dictated-text color format + sticky-format reset

**Why:** Dictated and typed text need to be visually distinguishable. Qt's "current char format" carries forward from the last `insertText` call, so we must explicitly reset it after commit or user typing inherits the dictation color.

**Files:**
- Modify: `src/ui/main_window.py`
- Modify: `tests/unit/test_main_window.py`

- [ ] **Step 3.1: Write failing tests**

Append to `tests/unit/test_main_window.py`:

```python
from PyQt6.QtGui import QColor, QTextCursor


DICTATION_COLOR = "#94e2d5"   # keep in sync with MainWindow.DICTATION_COLOR


def test_dictated_text_uses_dictation_color(qtbot):
    """commit_partial must apply the dictation_format foreground color."""
    window = MainWindow()
    qtbot.addWidget(window)

    window.begin_streaming()
    window.commit_partial("hello")

    # Inspect the format at position 0 of the inserted run
    cursor = window.editor.textCursor()
    cursor.setPosition(0)
    cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor)
    fmt = cursor.charFormat()
    assert fmt.foreground().color() == QColor(DICTATION_COLOR)


def test_typing_after_commit_uses_default_color(qtbot):
    """After commit_partial, the editor's current char format must revert to default,
    so user-typed text renders in the normal color, not the dictation color."""
    window = MainWindow()
    qtbot.addWidget(window)

    window.begin_streaming()
    window.commit_partial("dictated ")

    # Simulate user typing after the committed run
    cursor = window.editor.textCursor()
    cursor.insertText("typed")

    # Position is now at the end; step back one char and inspect format
    cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor)
    fmt = cursor.charFormat()
    assert fmt.foreground().color() != QColor(DICTATION_COLOR)
```

- [ ] **Step 3.2: Run the tests to verify they fail**

Run: `python -m pytest tests/unit/test_main_window.py::test_dictated_text_uses_dictation_color tests/unit/test_main_window.py::test_typing_after_commit_uses_default_color -v`
Expected: both FAIL — the dictation color isn't applied yet, and the sticky-format reset isn't implemented.

- [ ] **Step 3.3: Add `DICTATION_COLOR` class attribute and `_dictation_format`**

Edit `src/ui/main_window.py`. Near the top of the `MainWindow` class (before `__init__`), add:

```python
class MainWindow(QMainWindow):
    """Frameless floating dictation window with editable transcript."""

    DICTATION_COLOR = "#94e2d5"   # teal, distinct from the #cdd6f4 default text
```

Inside `__init__`, after `self._partial_start: int = -1`, add:

```python
        # Tracks the live partial's length so update_partial can replace
        # [_partial_start, _partial_start + _partial_len] in place.
        self._partial_len: int = 0

        # Format applied to every dictated run (partials and commits).
        self._dictation_format = QTextCharFormat()
        self._dictation_format.setForeground(QColor(self.DICTATION_COLOR))
        self._dictation_format.setFontItalic(False)
```

- [ ] **Step 3.4: Rework `commit_partial` to use `_dictation_format` and reset sticky format**

Replace the existing `commit_partial` method with:

```python
    def commit_partial(self, text: str):
        """Replace the live partial region with the final text and end streaming.

        After insertion the editor's current char format is reset to the default
        so subsequent user typing is not inadvertently rendered in the dictation color.
        """
        if self._partial_start < 0:
            if text:
                self.append_text(text)
            return

        cursor = self.editor.textCursor()
        cursor.setPosition(self._partial_start)
        cursor.setPosition(
            self._partial_start + self._partial_len,
            QTextCursor.MoveMode.KeepAnchor,
        )
        cursor.removeSelectedText()
        if text:
            cursor.insertText(text, self._dictation_format)

        self.editor.setTextCursor(cursor)
        # Reset the editor's current char format so subsequent user typing
        # reverts to the default color instead of inheriting the dictation format.
        self.editor.setCurrentCharFormat(QTextCharFormat())

        self._partial_start = -1
        self._partial_len = 0
        self.editor.ensureCursorVisible()
```

- [ ] **Step 3.5: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/test_main_window.py::test_dictated_text_uses_dictation_color tests/unit/test_main_window.py::test_typing_after_commit_uses_default_color -v`
Expected: both PASS.

- [ ] **Step 3.6: Run the full window test file for regressions**

Run: `python -m pytest tests/unit/test_main_window.py -v`
Expected: all tests pass. If `test_commit_partial`-style tests from Task 4 haven't been added yet, skip those; everything else should be green.

- [ ] **Step 3.7: Commit**

```bash
git add src/ui/main_window.py tests/unit/test_main_window.py
git commit -m "MainWindow: apply dictation color format and reset sticky format on commit"
```

---

## Task 4: Insert-at-cursor streaming partials

**Why:** Today, `begin_streaming` hard-codes the anchor to end-of-document. For insert-at-cursor dictation, the anchor must be the user's cursor position at the moment recording starts, and `update_partial` must replace `[_partial_start, _partial_start + _partial_len]` (not `[_partial_start, end]`) so text typed before recording (trailing it) is preserved.

**Files:**
- Modify: `src/ui/main_window.py`
- Modify: `tests/unit/test_main_window.py`

- [ ] **Step 4.1: Write failing tests**

Append to `tests/unit/test_main_window.py`:

```python
def test_insert_at_cursor_preserves_trailing_text(qtbot):
    """Streaming partials inserted mid-document must not eat the text that follows them."""
    window = MainWindow()
    qtbot.addWidget(window)

    # Seed the editor with "foo  bar" and position cursor between "foo " and "bar"
    window.editor.setPlainText("foo  bar")
    cursor = window.editor.textCursor()
    cursor.setPosition(4)   # between the two spaces
    window.editor.setTextCursor(cursor)

    window.begin_streaming()
    window.update_partial("one")
    window.update_partial("one two")
    window.commit_partial("one two three")

    assert window.editor.toPlainText() == "foo one two three bar"


def test_update_partial_shrinks_region_when_text_gets_shorter(qtbot):
    """If Whisper returns a shorter partial than the previous one, the replacement must
    leave no leftover characters from the longer previous partial."""
    window = MainWindow()
    qtbot.addWidget(window)

    window.editor.setPlainText("prefix suffix")
    cursor = window.editor.textCursor()
    cursor.setPosition(7)   # between "prefix " and "suffix"
    window.editor.setTextCursor(cursor)

    window.begin_streaming()
    window.update_partial("alpha beta gamma")
    window.update_partial("alpha")
    window.commit_partial("alpha")

    assert window.editor.toPlainText() == "prefix alphasuffix"


def test_commit_empty_partial_leaves_document_intact(qtbot):
    """Empty final transcription must remove the partial region and restore surrounding text."""
    window = MainWindow()
    qtbot.addWidget(window)

    window.editor.setPlainText("keep me")
    cursor = window.editor.textCursor()
    cursor.setPosition(4)
    window.editor.setTextCursor(cursor)

    window.begin_streaming()
    window.update_partial("junk that will go away")
    window.commit_partial("")

    assert window.editor.toPlainText() == "keep me"
```

- [ ] **Step 4.2: Run the tests to verify they fail**

Run: `python -m pytest tests/unit/test_main_window.py::test_insert_at_cursor_preserves_trailing_text tests/unit/test_main_window.py::test_update_partial_shrinks_region_when_text_gets_shorter tests/unit/test_main_window.py::test_commit_empty_partial_leaves_document_intact -v`
Expected: all FAIL — today's `update_partial` selects to end-of-doc so it eats the trailing text.

- [ ] **Step 4.3: Rework `begin_streaming` to anchor at cursor**

Edit `src/ui/main_window.py`. Replace `begin_streaming` with:

```python
    def begin_streaming(self):
        """Anchor a streaming partial region at the current cursor position.

        From this call until commit_partial, the range
        [_partial_start, _partial_start + _partial_len] is treated as the live
        partial. Everything outside that range is untouched.
        """
        cursor = self.editor.textCursor()
        self._partial_start = cursor.position()
        self._partial_len = 0
```

- [ ] **Step 4.4: Rework `update_partial` to replace in-place**

Replace `update_partial` with:

```python
    def update_partial(self, text: str):
        """Replace the current streaming partial with the latest live transcript.

        The replacement range is [_partial_start, _partial_start + _partial_len],
        so text before and after the partial is preserved regardless of how the
        partial grows or shrinks.
        """
        if self._partial_start < 0:
            return
        cursor = self.editor.textCursor()
        cursor.setPosition(self._partial_start)
        cursor.setPosition(
            self._partial_start + self._partial_len,
            QTextCursor.MoveMode.KeepAnchor,
        )
        cursor.removeSelectedText()
        cursor.insertText(text, self._dictation_format)
        self._partial_len = len(text)
        self.editor.ensureCursorVisible()
```

(Note: `commit_partial` was already updated in Task 3 to use `_partial_len`; confirm that step was completed and the `cursor.setPosition(self._partial_start + self._partial_len, ...)` form is in place.)

- [ ] **Step 4.5: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/test_main_window.py -v`
Expected: all tests pass.

- [ ] **Step 4.6: Commit**

```bash
git add src/ui/main_window.py tests/unit/test_main_window.py
git commit -m "MainWindow: anchor streaming partials at cursor, replace region in place"
```

---

## Task 5: Single Record toggle button

**Why:** Two side-by-side Record and Stop buttons are visual clutter and a redundant click target — only one is valid at any moment. A single toggle that flips label/color is simpler and matches the single `handle_trigger(bool)` semantics we already have.

**Files:**
- Modify: `src/ui/main_window.py`
- Modify: `tests/unit/test_main_window.py`

- [ ] **Step 5.1: Write failing tests**

Append to `tests/unit/test_main_window.py`:

```python
def test_single_record_button_label_starts_at_record(qtbot):
    """Before recording, the toggle button shows 'Record'."""
    window = MainWindow()
    qtbot.addWidget(window)
    assert "Record" in window.record_btn.text()


def test_single_record_button_flips_label_while_recording(qtbot):
    """set_recording_state(True) flips the toggle to the Stop label."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.set_recording_state(True)
    assert "Stop" in window.record_btn.text()
    window.set_recording_state(False)
    assert "Record" in window.record_btn.text()


def test_single_record_button_fires_correct_boolean(qtbot):
    """Clicking toggles between True and False via on_toggle_recording."""
    window = MainWindow()
    qtbot.addWidget(window)

    fired = []
    window.on_toggle_recording = lambda pressed: fired.append(pressed)

    # Idle → click emits True
    window.record_btn.click()
    assert fired == [True]

    # Recording → click emits False
    window.set_recording_state(True)
    window.record_btn.click()
    assert fired == [True, False]


def test_stop_btn_attribute_is_gone(qtbot):
    """The separate stop_btn must be removed — the single record_btn handles both states."""
    window = MainWindow()
    qtbot.addWidget(window)
    assert not hasattr(window, "stop_btn")
```

- [ ] **Step 5.2: Run the tests to verify they fail**

Run: `python -m pytest tests/unit/test_main_window.py -k "single_record or stop_btn_attribute" -v`
Expected: failures — `stop_btn` still exists, `record_btn` doesn't flip label.

- [ ] **Step 5.3: Remove the `stop_btn` widget and consolidate click handling**

Edit `src/ui/main_window.py`. In the action-bar construction block (approximately lines 110-122), replace:

```python
        self.record_btn = QPushButton("● Record")
        self.record_btn.setObjectName("recordBtn")
        self.record_btn.setToolTip("Start recording (F4)")
        self.record_btn.clicked.connect(self._on_record_clicked)
        ab.addWidget(self.record_btn)

        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setToolTip("Stop recording (F4)")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        ab.addWidget(self.stop_btn)
```

with:

```python
        # Single toggle — text/tooltip/objectName flip based on recording state.
        self.record_btn = QPushButton("● Record")
        self.record_btn.setObjectName("recordBtn")
        self.record_btn.setToolTip("Start recording (F4)")
        self.record_btn.clicked.connect(self._on_record_toggle_clicked)
        ab.addWidget(self.record_btn)
```

Also track recording state locally so the toggle click knows which boolean to emit. Inside `__init__`, near `self._partial_start`, add:

```python
        self._recording: bool = False
```

- [ ] **Step 5.4: Replace the two click handlers with a single toggle handler**

Replace the `_on_record_clicked` and `_on_stop_clicked` methods with:

```python
    def _on_record_toggle_clicked(self):
        """Single toggle: emits True if currently idle, False if currently recording."""
        if self.on_toggle_recording is not None:
            self.on_toggle_recording(not self._recording)
```

- [ ] **Step 5.5: Update `set_recording_state` to flip label and track state**

Replace `set_recording_state` with:

```python
    def set_recording_state(self, recording: bool):
        """Reflect recording state: flip the single toggle and lock mic-row widgets."""
        self._recording = recording
        if recording:
            self.record_btn.setText("■ Stop")
            self.record_btn.setToolTip("Stop recording (F4)")
            self.record_btn.setObjectName("stopBtn")
        else:
            self.record_btn.setText("● Record")
            self.record_btn.setToolTip("Start recording (F4)")
            self.record_btn.setObjectName("recordBtn")
        # Re-apply stylesheet so the objectName-based rule refreshes
        self.record_btn.style().unpolish(self.record_btn)
        self.record_btn.style().polish(self.record_btn)

        self.mic_combo.setEnabled(not recording)
        self.refresh_btn.setEnabled(not recording)
```

- [ ] **Step 5.6: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/test_main_window.py -v`
Expected: all tests pass.

- [ ] **Step 5.7: Commit**

```bash
git add src/ui/main_window.py tests/unit/test_main_window.py
git commit -m "MainWindow: consolidate Record/Stop into a single toggle button"
```

---

## Task 6: Dictation-mode toggle (In-app / Wedge)

**Why:** Users should be able to dictate into the in-app editor (radiology workflow) or into any externally focused window (Chrome/Gmail/Outlook) without restarting the app. The toggle is a two-item `QComboBox` placed above the mic row.

**Files:**
- Modify: `src/ui/main_window.py`
- Modify: `tests/unit/test_main_window.py`

- [ ] **Step 6.1: Write failing tests**

Append to `tests/unit/test_main_window.py`:

```python
def test_mode_toggle_defaults_to_inapp(qtbot):
    """Fresh window must start in In-app mode."""
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.current_mode() == "inapp"
    assert not window.editor.isReadOnly()


def test_set_dictation_mode_wedge_locks_editor(qtbot):
    """Switching to Wedge mode makes the editor read-only."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.set_dictation_mode("wedge")
    assert window.current_mode() == "wedge"
    assert window.editor.isReadOnly()


def test_set_dictation_mode_back_to_inapp_unlocks(qtbot):
    """Switching Wedge → In-app unlocks the editor again."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.set_dictation_mode("wedge")
    window.set_dictation_mode("inapp")
    assert window.current_mode() == "inapp"
    assert not window.editor.isReadOnly()


def test_mode_toggle_disabled_during_recording(qtbot):
    """The mode combo must be disabled while recording."""
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.mode_combo.isEnabled()
    window.set_recording_state(True)
    assert not window.mode_combo.isEnabled()
    window.set_recording_state(False)
    assert window.mode_combo.isEnabled()


def test_mode_combo_change_fires_callback(qtbot):
    """Changing the combo selection emits the new mode string via on_mode_changed."""
    window = MainWindow()
    qtbot.addWidget(window)
    received = []
    window.on_mode_changed = lambda m: received.append(m)
    window.mode_combo.setCurrentIndex(1)   # Wedge
    assert received == ["wedge"]


def test_editor_is_read_only_during_recording_in_inapp_mode(qtbot):
    """Spec: editor is locked during recording in In-app mode, editable when idle."""
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.current_mode() == "inapp"
    assert not window.editor.isReadOnly()

    window.set_recording_state(True)
    assert window.editor.isReadOnly()

    window.set_recording_state(False)
    assert not window.editor.isReadOnly()


def test_editor_stays_read_only_across_recording_in_wedge_mode(qtbot):
    """In Wedge mode, the editor is read-only whether recording or idle."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.set_dictation_mode("wedge")
    assert window.editor.isReadOnly()

    window.set_recording_state(True)
    assert window.editor.isReadOnly()

    window.set_recording_state(False)
    assert window.editor.isReadOnly()
```

- [ ] **Step 6.2: Run the tests to verify they fail**

Run: `python -m pytest tests/unit/test_main_window.py -k "mode" -v`
Expected: all new mode tests FAIL — `current_mode`, `mode_combo`, `set_dictation_mode`, and `on_mode_changed` don't exist yet.

- [ ] **Step 6.3: Add the `on_mode_changed` hook**

Edit `src/ui/main_window.py`. In `__init__`, alongside the existing hook attributes, add:

```python
        self.on_mode_changed: Optional[Callable[[str], None]] = None
```

- [ ] **Step 6.4: Add the mode row above the mic row**

In `__init__`, immediately before the block that creates `mic_row` (approximately line 80), add:

```python
        # Dictation mode row — In-app (default) or Wedge (send to focused external app)
        mode_row = QWidget()
        mode_row.setObjectName("modeRow")
        mdr = QHBoxLayout(mode_row)
        mdr.setContentsMargins(10, 4, 10, 0)
        mdr.setSpacing(6)

        mode_label = QLabel("Mode:")
        mode_label.setObjectName("modeLabel")
        mdr.addWidget(mode_label)

        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("modeCombo")
        self.mode_combo.setToolTip(
            "In-app: dictate into this editor. "
            "Wedge: dictate into whatever external window has focus."
        )
        self.mode_combo.addItem("In-app", userData="inapp")
        self.mode_combo.addItem("Wedge (any focused window)", userData="wedge")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_combo_changed)
        mdr.addWidget(self.mode_combo, stretch=1)

        root.addWidget(mode_row)
```

- [ ] **Step 6.5: Add `current_mode`, `set_dictation_mode`, and the combo handler**

Append these methods to the `MainWindow` class (near the other public API methods):

```python
    def current_mode(self) -> str:
        """Return the active dictation mode: 'inapp' or 'wedge'."""
        data = self.mode_combo.currentData()
        return data if data else "inapp"

    def set_dictation_mode(self, mode: str):
        """Apply a dictation mode: locks the editor in Wedge, unlocks in In-app."""
        if mode == "wedge":
            self.editor.setReadOnly(True)
        else:
            self.editor.setReadOnly(False)
        # Sync combo if called programmatically
        for i in range(self.mode_combo.count()):
            if self.mode_combo.itemData(i) == mode:
                if self.mode_combo.currentIndex() != i:
                    self.mode_combo.blockSignals(True)
                    self.mode_combo.setCurrentIndex(i)
                    self.mode_combo.blockSignals(False)
                break

    def _on_mode_combo_changed(self, idx: int):
        if idx < 0:
            return
        mode = self.mode_combo.itemData(idx)
        if not mode:
            return
        self.set_dictation_mode(mode)
        if self.on_mode_changed is not None:
            self.on_mode_changed(mode)
```

- [ ] **Step 6.6: Disable the mode combo during recording and lock the editor in-app**

In the `set_recording_state` method (defined in Task 5), add the following lines at the end of the body:

```python
        self.mode_combo.setEnabled(not recording)
        # Editor lock: always read-only while recording (prevents collision with
        # the live partial region). When idle, read-only state follows the mode.
        self.editor.setReadOnly(recording or self.current_mode() == "wedge")
```

- [ ] **Step 6.7: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/test_main_window.py -v`
Expected: all tests pass.

- [ ] **Step 6.8: Commit**

```bash
git add src/ui/main_window.py tests/unit/test_main_window.py
git commit -m "MainWindow: add In-app/Wedge dictation mode toggle"
```

---

## Task 7: Wire mode toggle and streaming gating in main.py

**Why:** `MainWindow` exposes the mode but doesn't drive behavior — `main.py` owns the orchestrator, the streaming transcriber, and the trigger handler. The trigger handler now reads the mode on Stop and passes it to `orchestrator.handle_trigger_up`. In Wedge mode, streaming is not started (no UI to render partials into) and the finalized text is appended to the editor as a history line.

**Files:**
- Modify: `src/main.py`

- [ ] **Step 7.1: Update `handle_trigger` to branch on mode**

Edit `src/main.py`. Replace the existing `handle_trigger` function (approximately lines 73-96) with:

```python
    def handle_trigger(pressed: bool):
        # Idempotent: clicking Record while already recording (or Stop while idle)
        # is a no-op. Keeps HID, F4, and button sources consistent.
        if pressed == recording_state["active"]:
            return
        recording_state["active"] = pressed
        mode = window.current_mode()
        window.set_recording_state(pressed)

        if pressed:
            if mode == "wedge":
                window.set_status("Recording (Wedge)...", "#f38ba8")
                orchestrator.handle_trigger_down()
                # No streaming in Wedge mode: partials have nowhere to render.
            else:
                window.set_status("Recording...", "#f38ba8")
                window.begin_streaming()
                orchestrator.handle_trigger_down()
                streaming.start()
        else:
            window.set_status("Processing...", "#fab387")
            if mode == "inapp":
                streaming.stop()
            result = orchestrator.handle_trigger_up(mode=mode)
            if mode == "wedge":
                if result:
                    window.append_text(result)
                    window.set_status("Ready")
                else:
                    window.set_status("No text recognized", "#f9e2af")
            else:
                if result:
                    window.commit_partial(result)
                    window.set_status("Ready")
                else:
                    window.commit_partial("")
                    window.set_status("No text recognized", "#f9e2af")
```

- [ ] **Step 7.2: Wire `on_mode_changed` with a status hint**

Edit `src/main.py`. After the existing `window.on_mic_changed = on_mic_changed` block (approximately line 108), add:

```python
    def on_mode_changed(mode: str):
        # Ignore mid-recording (the UI also disables the combo, but guard here too).
        if recording_state["active"]:
            return
        if mode == "wedge":
            window.set_status(
                "Wedge mode — click into the target window, then hold the mic",
                "#89b4fa",
            )
        else:
            window.set_status("Ready")
        logger.info(f"Dictation mode: {mode}")

    window.on_mode_changed = on_mode_changed
```

- [ ] **Step 7.3: Smoke-test the full app**

Run: `python -m src.main`

Manual checks (the user will run these; record the expected behavior here so the executor knows what "works" looks like):
1. Window launches in In-app mode. Editor is editable; type something — text appears in default color.
2. Click mid-line, press F4, speak a word, release (or click Stop). The dictated word appears at the cursor position in teal (#94e2d5).
3. Toggle to Wedge, focus Notepad, press F4, speak, release. Text types into Notepad; the sent utterance is appended to the in-app editor as a history line.
4. Toggle back to In-app; editor is editable again; history remains.
5. Start recording; mode combo, mic combo, and refresh button are greyed out. Stop; all three re-enable.

- [ ] **Step 7.4: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: all tests pass.

- [ ] **Step 7.5: Commit**

```bash
git add src/main.py
git commit -m "main.py: route handle_trigger by mode; wedge skips streaming, logs history"
```

---

## Task 8: Resizable window via `QSizeGrip`

**Why:** The frameless floating window can't be resized today. Add a size grip in the bottom-right corner so the editor can grow without breaking the floating/always-on-top aesthetic.

**Files:**
- Modify: `src/ui/main_window.py`
- Modify: `tests/unit/test_main_window.py`

- [ ] **Step 8.1: Write failing test**

Append to `tests/unit/test_main_window.py`:

```python
from PyQt6.QtWidgets import QSizeGrip


def test_window_has_size_grip(qtbot):
    """A QSizeGrip must be present for frameless resize."""
    window = MainWindow()
    qtbot.addWidget(window)
    grips = window.findChildren(QSizeGrip)
    assert len(grips) >= 1
```

- [ ] **Step 8.2: Run the test to verify it fails**

Run: `python -m pytest tests/unit/test_main_window.py::test_window_has_size_grip -v`
Expected: FAIL — no `QSizeGrip` in the widget tree yet.

- [ ] **Step 8.3: Add the `QSizeGrip` import and widget**

Edit `src/ui/main_window.py`. Update the import line to include `QSizeGrip`:

```python
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QPushButton, QComboBox, QSizeGrip,
)
```

At the end of `__init__` (after `self.set_status("Ready")` — or just before it is fine too), add:

```python
        # Frameless windows lack native resize handles; a QSizeGrip in the
        # bottom-right provides a visible drag target without re-enabling the frame.
        grip = QSizeGrip(root_widget)
        grip.setFixedSize(14, 14)
        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 2, 2)
        grip_row.addStretch()
        grip_row.addWidget(grip)
        root.addLayout(grip_row)
```

- [ ] **Step 8.4: Run the test to verify it passes**

Run: `python -m pytest tests/unit/test_main_window.py::test_window_has_size_grip -v`
Expected: PASS.

- [ ] **Step 8.5: Run the full window test file for regressions**

Run: `python -m pytest tests/unit/test_main_window.py -v`
Expected: all tests pass.

- [ ] **Step 8.6: Commit**

```bash
git add src/ui/main_window.py tests/unit/test_main_window.py
git commit -m "MainWindow: add QSizeGrip for frameless resize"
```

---

## Task 9: Profiling pass

**Why:** The project has a sub-200ms latency mandate. New in-editor text manipulation (`update_partial` replacing a region as the document grows) is an unknown; adding spans to `utils/profiler.py` surfaces regressions before they become chronic.

**Files:**
- Modify: `src/ui/main_window.py`
- Modify: `src/main.py` (optional — if we want the timer accessible)

- [ ] **Step 9.1: Wire an optional profiler into MainWindow**

Edit `src/ui/main_window.py`. In `__init__`, add one attribute:

```python
        self.profiler = None   # main.py sets this to the shared LatencyTimer
```

Inside `update_partial`, wrap the replacement block:

```python
    def update_partial(self, text: str):
        if self._partial_start < 0:
            return
        if self.profiler:
            self.profiler.start("partial_replace")
        cursor = self.editor.textCursor()
        cursor.setPosition(self._partial_start)
        cursor.setPosition(
            self._partial_start + self._partial_len,
            QTextCursor.MoveMode.KeepAnchor,
        )
        cursor.removeSelectedText()
        cursor.insertText(text, self._dictation_format)
        self._partial_len = len(text)
        self.editor.ensureCursorVisible()
        if self.profiler:
            self.profiler.stop("partial_replace")
```

Inside `set_dictation_mode`, wrap likewise:

```python
    def set_dictation_mode(self, mode: str):
        if self.profiler:
            self.profiler.start("mode_switch")
        if mode == "wedge":
            self.editor.setReadOnly(True)
        else:
            self.editor.setReadOnly(False)
        for i in range(self.mode_combo.count()):
            if self.mode_combo.itemData(i) == mode:
                if self.mode_combo.currentIndex() != i:
                    self.mode_combo.blockSignals(True)
                    self.mode_combo.setCurrentIndex(i)
                    self.mode_combo.blockSignals(False)
                break
        if self.profiler:
            self.profiler.stop("mode_switch")
```

- [ ] **Step 9.2: Share the profiler from main.py**

Edit `src/main.py`. After the `window = MainWindow()` line (approximately line 63), add:

```python
    window.profiler = profiler
```

- [ ] **Step 9.3: Run a long-dictation smoke session**

Launch: `python -m src.main`

Manual procedure:
1. In-app mode. Dictate continuously for ~60 seconds. Pause. Commit.
2. Watch the log for `Task 'partial_replace' took X.XXXXs` debug lines.
3. Flag any `partial_replace` reading > 0.050s (50 ms) — at 1.5 s ticks that is a hard upper bound before UX starts to jitter. Anything > 0.200s violates the Core Mandate #2 budget and warrants a follow-up issue.
4. Toggle modes a few times; `mode_switch` timings should all be < 1 ms.

Record findings (even informally — "no outliers" counts) in the commit message.

- [ ] **Step 9.4: Commit**

```bash
git add src/ui/main_window.py src/main.py
git commit -m "Profiler: add partial_replace and mode_switch spans for latency watch"
```

---

## Task 10: Dead-code + readability sweep

**Why:** Standing preference for this project: every implementation plan ends with a dead-code + readability pass. Keeps the codebase tight as slices accumulate and surfaces files that have outgrown their 150-line budget.

**Files:**
- Inspect: `src/ui/main_window.py`, `src/main.py`, `src/core/orchestrator.py`

- [ ] **Step 10.1: Unused-import sweep**

Run from the repo root:

```bash
python -m pyflakes src/ui/main_window.py src/main.py src/core/orchestrator.py
```

If `pyflakes` is not installed, use grep instead:

```bash
python -c "import ast, sys; m = ast.parse(open('src/ui/main_window.py').read()); [print(n.names[0].name) for n in ast.walk(m) if isinstance(n, ast.ImportFrom)]"
```

For each import reported unused, remove it and commit the removal as part of Step 10.5.

- [ ] **Step 10.2: Orphaned-handler sweep**

Search for `_on_` methods in `main_window.py` that aren't called or connected:

Using Grep tool: pattern `_on_[a-z_]+`, path `src/ui/main_window.py`.

For each match, confirm it is either:
- Connected to a Qt signal via `.connect(self._on_...)`, or
- Called by another method in the class.

Remove any that are neither.

- [ ] **Step 10.3: Comment-and-docstring freshness pass**

Per this project's moderate-comment-density standard:
- Every non-trivial new function must have a one-line intent comment above it (already added in Tasks 3-8).
- Re-read `main_window.py`, `main.py`, `orchestrator.py`. For each comment: does it explain **why**, or is it narrating the **what**? Delete any that narrate the what. Fix any that are stale (e.g., mention Stop button that no longer exists).

- [ ] **Step 10.4: File-size budget check**

Run:

```bash
wc -l src/ui/main_window.py src/main.py src/core/orchestrator.py src/core/streaming.py
```

Expected after this slice:
- `main_window.py`: ~500 lines (over the 150-line budget from Developer Instruction #1).
- `main.py`: ~200 lines.
- `orchestrator.py`: well under.
- `streaming.py`: well under.

**Do not refactor `main_window.py` in this slice.** Instead, append a follow-up note to the project plan:

Edit `docs/superpowers/plans/project-plan.md`. In the "Known Issues & Next Steps" section, add a bullet:

```markdown
- **main_window.py size budget exceeded** — After the editable-transcript slice
  (2026-04-21), main_window.py is ~500 lines, over the 150-line per-file budget.
  Next slice should extract a `DictationEditor` widget class that owns the
  partial-tracking state and the dictation_format, leaving MainWindow as a pure
  layout/wiring shell.
```

- [ ] **Step 10.5: Commit whatever the sweep produced**

If any code was removed or any comments were rewritten, commit under one message. If nothing was removed, still commit the project-plan.md follow-up note:

```bash
git add -A
git commit -m "Sweep: remove unused code; note main_window.py size follow-up"
```

If there were genuinely no changes and no follow-up to add, skip this step.

---

## Final verification

- [ ] **Step Final.1: Full test suite**

Run: `python -m pytest tests/ -v`
Expected: all tests pass.

- [ ] **Step Final.2: Full manual test plan from the spec**

Run the 7-step manual plan in the spec's "Manual test plan" section. Confirm each step behaves as described.

- [ ] **Step Final.3: Mark Phase 8.2 done in project-plan.md**

Edit `docs/superpowers/plans/project-plan.md`. Below the existing Task 8.1 entry, add:

```markdown
### Task 8.2: Editable Transcript + Insert-at-Cursor + Mode Toggle ✅
**Added:** In-app transcript is now editable with insert-at-cursor streaming
dictation. Dictated text renders in a distinct teal color against typed text
in default color. Single Record toggle replaces the Record/Stop pair. Window
is resizable via a bottom-right QSizeGrip. New mode toggle at the top of the
window: **In-app** (default; dictation lands in the editor) vs **Wedge**
(dictation routes to the focused external window via SendInput; the editor
becomes a read-only scrolling history). Orchestrator grows a `mode` parameter
that gates the keyboard wedge call. Streaming partials are not started in
Wedge mode. Spec: `docs/superpowers/specs/2026-04-21-editable-transcript-design.md`.
```

- [ ] **Step Final.4: Commit**

```bash
git add docs/superpowers/plans/project-plan.md
git commit -m "Project plan: mark Phase 8.2 editable-transcript slice done"
```
