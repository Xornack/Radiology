# Design: Editable Transcript with Insert-at-Cursor Dictation

**Date:** 2026-04-21
**Status:** Approved for implementation planning
**Slice:** 1 of N on the road to PowerScribe-D parity

## Purpose

Convert the read-only in-app transcript into an editable document that accepts dictation at the current cursor position, and add a mode switch so the same app can dictate either into its own editor or into any externally focused window (Chrome, Gmail, Outlook, Epic) via the existing keyboard wedge.

This is the first slice toward PowerScribe-level editing. Voice navigation, voice editing, field templates, macros, and TTS readback are explicitly deferred to subsequent slices.

## Non-goals

- Voice navigation commands ("go to end", "next paragraph" beyond existing `punctuation.py` tokens).
- Voice editing commands ("delete that", "correct X to Y").
- Field/placeholder templates (`[AORTA]`) and macros.
- TTS readback.
- Push-to-talk / dead-man-switch for the SpeechMike (deferred but designed around — a future one-line flag).
- Persistence across sessions / crash recovery.
- Save/export actions (copy-to-clipboard, save-to-file, save-to-EHR).

## Scope of this slice

1. **Editable transcript** — the in-app `QTextEdit` is no longer `setReadOnly(True)`. User can click, arrow, select, type, delete.
2. **Insert-at-cursor streaming dictation** — when recording starts, the cursor position at that moment is the insertion anchor. Streaming partials refine in-place as normal text (no italics). Surrounding text pushes rightward naturally.
3. **Dictated-text color coding** — dictated text renders in a distinct color via a dedicated `QTextCharFormat`; typed text inherits the editor default. Trivial given the existing formatting infrastructure.
4. **Single Record toggle button** — replaces the separate Record + Stop buttons. Label and color flip with recording state. F4 and the SpeechMike trigger continue to share the same handler.
5. **Resizable window** — `QSizeGrip` docked bottom-right. Frameless look preserved.
6. **Dictation-mode toggle** — single switch at the top of the window:
   - **In-app** (default): dictation lands in the editable transcript only. External apps untouched.
   - **Wedge**: editor is locked read-only. Dictation is routed to the focused external window via `SendInput`. Finalized utterances are appended to the editor as a read-only scrolling history so the user can audit what was sent.
7. **Editor locked during recording in In-app mode** — matches existing mic-combo lock behavior. Prevents the partial insertion region from desyncing.

## Architecture

Three existing files carry the change; one new test file is added. No new modules. The scope is kept small on purpose.

### `src/ui/main_window.py`

- Remove `setReadOnly(True)` on construction; add `setReadOnly(True)` in `set_dictation_mode("wedge")` and `setReadOnly(False)` in `set_dictation_mode("inapp")` (subject to recording lock).
- Add a **mode row** at the top with a `QComboBox` containing "In-app" and "Wedge (any focused window)". Exposes:
  - `on_mode_changed: Optional[Callable[[str], None]]` callback hook.
  - `current_mode() -> str` accessor, returning `"inapp"` or `"wedge"`.
  - `set_dictation_mode(mode: str)` which adjusts editor read-only state and status hint text.
- Replace `record_btn` + `stop_btn` pair with a **single `record_btn`** whose label, icon, and object-name flip between "● Record" / "■ Stop" states. Pressing it calls `on_toggle_recording(not recording)`.
- Add `QSizeGrip` in the bottom-right corner of the root layout. Remove any fixed-size assumptions; keep the 460×310 default as a minimum or initial size, not a cap.
- Rework streaming helpers to anchor at cursor:
  - `begin_streaming()` — snapshot `cursor.position()` as `_partial_start`; set `_partial_len = 0`.
  - `update_partial(text)` — select `[_partial_start, _partial_start + _partial_len]`, remove it, reinsert `text` using `self.dictation_format`; update `_partial_len = len(text)`.
  - `commit_partial(final_text)` — same replace, final-text in `self.dictation_format`, reset `_partial_start = -1`, move cursor to the end of the insertion.
- Define `self.dictation_format: QTextCharFormat` with a distinct foreground color (proposal: `#94e2d5` teal from the catppuccin palette already in use). Not italic. Applied to every partial + commit insertion.
- After `commit_partial`, reset the editor cursor's current char format back to the editor default. Otherwise Qt's "current char format" stays sticky from the last `insertText`, and subsequent user typing would appear in the dictation color. The test "text typed after commit reverts to default" guards this.
- `set_recording_state(recording)` additionally disables the mode toggle and the record-button toggle path while recording.

### `src/core/orchestrator.py`

- `handle_trigger_up` grows a `mode: str = "inapp"` parameter.
- Record → STT → scrub → punctuation pipeline unchanged.
- Only the final branch changes:
  - `mode == "inapp"` → return the text; do **not** call the wedge.
  - `mode == "wedge"` → call `wedge.type_text(text)` (inside the existing try/except); return the text regardless.

### `src/main.py`

- Read `window.current_mode()` inside `handle_trigger(False)` and pass it to `orchestrator.handle_trigger_up(mode=…)`. No separate state variable.
- Wire `window.on_mode_changed = on_mode_changed`. The callback:
  - No-ops if `recording_state["active"]` is True (defensive; UI also disables the toggle).
  - Calls `window.set_dictation_mode(mode)`.
  - In **In-app** mode: ensures the streaming transcriber is wired (`streaming.partial_ready.connect(window.update_partial)` idempotently).
  - In **Wedge** mode: disconnects the streaming partial signal and ensures streaming is stopped (no wasted CPU transcribing partials that never render).
- On Stop in **Wedge** mode, append the returned final text to the editor via `window.append_text(text)` so the user sees a history log.

### `src/core/streaming.py`

No interface changes. Consumer decides whether to render partials at the cursor or end-of-document — that decision lives in `MainWindow`.

## Data flow

### In-app mode (default)

1. User positions cursor anywhere and types freely.
2. Press Record → `handle_trigger(True)`.
3. `begin_streaming()` captures cursor position; editor goes read-only; status → "Recording…".
4. Every ~1.5 s, `StreamingTranscriber` emits `partial_ready(text)`.
5. `update_partial(text)` replaces the partial region in place, in dictation color.
6. Stop → `handle_trigger(False)` → `orchestrator.handle_trigger_up(mode="inapp")` returns final text.
7. `commit_partial(final_text)` replaces partial region with final text, resets bookkeeping, unlocks editor. Status → "Ready".

### Wedge mode

1. User toggles mode to "Wedge". Editor becomes read-only; hint text: "Click into the target window, then hold the mic."
2. User focuses Chrome/Outlook/etc.
3. Press Record → `handle_trigger(True)`. Streaming is **not started**. `recorder.start()`. Status → "Recording (Wedge)".
4. Stop → `orchestrator.handle_trigger_up(mode="wedge")` → `wedge.type_text(final)` → returns text.
5. `window.append_text(final)` logs the sent utterance in the editor. Status → "Ready".

### Mode switching

- Only allowed when not recording (UI disables it; callback also guards).
- Editor content is **never** cleared on switch. In-app → Wedge: current text becomes the start of the history log. Wedge → In-app: editor unlocks with existing content intact.

## Error handling & edge cases

- **Cursor at end of document** works identically to today.
- **Whisper returns shorter partial than previous** — the `[_partial_start, _partial_start + _partial_len]` replace covers this; no leftover characters.
- **Empty final transcription** — `commit_partial("")` removes the partial region and restores surrounding text untouched. Existing `if clean_text` guard in `orchestrator` prevents wedge call on empty text.
- **User attempts to edit during recording** — editor is read-only; UI disables; defensive no-op in `on_mode_changed` if `recording_state["active"]` is True.
- **Wedge failure** (existing try/except in orchestrator) — text still returned; in Wedge mode it is appended to the history log. Status → "Wedge send failed — text logged".
- **External focus is our own app in Wedge mode** — `SendInput` sends to self; acceptable, hint message ("Click into the target window, then hold the mic") is the mitigation. A focus-check via Win32 is out of scope.
- **Document modified programmatically during recording** — cannot happen in this slice (editor is locked, no other code path writes during recording). `_partial_start` is a plain integer; noted as a latent assumption.

## Back-compatibility

- `DictationOrchestrator.handle_trigger_up()` defaults `mode="inapp"`. Existing test `tests/integration/test_orchestrator.py` that asserts `wedge.type_text` was called is updated to pass `mode="wedge"` explicitly.
- Existing Record/Stop tests in `tests/unit/test_main_window.py` are rewritten around the single toggle; separate-button assertions are removed.

## Testing

### Unit (`tests/unit/test_main_window.py`, extensions)

- Editor is editable after construction.
- Mode toggle starts in "In-app"; switching to "Wedge" locks the editor; switching back unlocks.
- Mode toggle is disabled during `set_recording_state(True)` and re-enabled on `False`.
- Single record button: starts as "Record"; `set_recording_state(True)` flips to "Stop"; clicking in each state fires `on_toggle_recording` with the correct boolean.
- Resize grip (`QSizeGrip`) is present in the layout.
- `begin_streaming()` → `update_partial("one")` → `update_partial("one two")` → `commit_partial("one two three")` with cursor at position N: text at `[N, N + len("one two three")]` equals "one two three"; text before and after position N untouched.
- Dictated text carries the dictation color format; text typed after commit reverts to the editor default format.
- `commit_partial("")` removes the partial region cleanly and restores surrounding text.

### Unit (`tests/unit/test_orchestrator.py`, new)

- `handle_trigger_up(mode="inapp")` returns transcribed text; `wedge.type_text` is **not** called.
- `handle_trigger_up(mode="wedge")` returns text **and** calls `wedge.type_text(text)` exactly once.
- `handle_trigger_up(mode="wedge")` with empty transcription does **not** call the wedge (existing `if clean_text` guard).

### Integration (`tests/integration/test_orchestrator.py`, updated)

- Existing wedge-call test passes `mode="wedge"` explicitly.
- New case: `mode="inapp"` skips the wedge.

### Manual test plan (for the user after the slice lands)

1. Launch; verify window resizes via the bottom-right grip.
2. In-app mode: click mid-sentence, dictate a word; verify it appears at the cursor in the dictation color.
3. In-app mode: type after the commit; verify it appears in the default color.
4. In-app mode: stream a long sentence; verify it refines in place without eating adjacent typed text.
5. Toggle to Wedge with Notepad focused; dictate; verify text types into Notepad and also appears in the in-app history.
6. Toggle back to In-app; verify editor is editable and the history persists as regular text.
7. Start recording; verify mode toggle is greyed out. Stop; verify it re-enables.

## Profiling pass (final plan step)

- Add `profiler` spans for:
  - `partial_replace` — time per `update_partial` call.
  - `mode_switch` — time per mode toggle.
- Run a long dictation (>60 s) in In-app mode; export timings; flag any >200 ms outliers against Core Mandate #2 (sub-200 ms).
- If `partial_replace` dominates as the document grows, file a follow-up — a VAD-based committed/in-flight split is already called out in `project-plan.md` as a future item.

## Dead-code + readability sweep (final plan step)

- `rg` pass for unused imports, orphaned helpers, and dead branches in the files touched.
- Re-read `main_window.py`, `main.py`, `orchestrator.py` end-to-end. Look for functions that could be one-lined, one-liners that deserve names, stale comments.
- Confirm file-size budget (Developer Instruction #1: no file > 150 lines). `main_window.py` is already ~386 lines pre-slice and will grow. Do **not** refactor in this slice; file a follow-up to extract a `DictationEditor` widget class in a subsequent slice.

## Slice boundary check

Per the user's standing preference for small, thoroughly-tested slices: this slice ends at a stable, usable working state. The user exercises it, files issues, confirms, and only then do we design the next slice (candidates: push-to-talk / hands-free toggle; voice navigation; field templates; TTS readback).
