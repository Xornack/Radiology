# Design: PowerScribe-style fields (slice 1 — navigation + dictate-replace)

**Date:** 2026-04-26
**Status:** Approved for implementation planning
**Slice:** First step toward the PowerScribe-D end state (field templates +
macros). Scope deliberately small: anchored bracket fields, Ctrl+Tab
navigation, dictate-to-replace. No template loader, no pick-lists, no
voice "next field," no sign-time guardrails.

## Purpose

The editor today is a single block of free dictation. To move toward a
PowerScribe-style workflow, the user wants to author or paste templates
that include placeholder fields (e.g., `[normal]`) and tab between them
to dictate over each placeholder in turn. This spec wires the smallest
possible version of that behavior: detect bracket-delimited fields,
visually distinguish them, navigate with Ctrl+Tab / Ctrl+Shift+Tab, and
let the existing dictation pipeline replace a selected field cleanly.

The user is a radiologist who uses PowerScribe daily and wants the
muscle memory carried over without copying its trade dress (red
brackets) or proprietary terminology ("AutoText").

## Non-goals

- **Template library / loader.** Test by typing or pasting bracket text
  into the editor. A "Load template" UI is the natural next slice.
- **Pick-list fields.** PowerScribe also has dropdowns inside fields.
  Out of scope here; will hang off the same `FieldAnchor` later.
- **Voice "next field" command.** STT post-processing concern; separate
  slice once spoken-punctuation patterns are settled.
- **Sign-time warning for unfilled fields.** No "Sign report" action
  exists yet to attach a guard to.
- **SpeechMic button / hotkey remapping.** The user explicitly wants
  Ctrl+Tab now and remappability later. We choose Ctrl+Tab so the
  remap layer can replace it cleanly without UX churn.
- **Mouse-click-into-field auto-selects whole field.** v1 just moves the
  cursor on click; selection-on-Tab is the only entry mode.

## Decisions captured during brainstorm

1. **Marker syntax:** `[default text]`. Brackets included in the regex
   match. The placeholder text inside the brackets is the field's
   default (left in place if the user tabs past without dictating).
2. **Visual style B (highlight pill):** unfilled fields render as a
   lavender rounded pill. Brackets stay in the underlying text model
   for regex detection but are color-matched to the pill background so
   they read invisibly. Active/focused field gets an additional yellow
   outline. Filled fields drop the pill entirely and inherit the
   existing dictation-teal color from `MainWindow.DICTATION_COLOR`.
3. **Navigation keys:** **Ctrl+Tab** = next field, **Ctrl+Shift+Tab** =
   previous field. Plain `Tab` keeps inserting a `\t` character (the
   user dictates around `Tab` in PowerScribe today and finds losing
   the literal tab key annoying).
4. **Selection on focus:** Ctrl+Tab onto a field selects the *full*
   `[default]` range (brackets included) so the existing
   `TextStreamingController.begin()` removes-on-selection behavior
   replaces it cleanly when the user records.
5. **Wrap-around:** Ctrl+Tab past the last field wraps to the first.
   Ctrl+Shift+Tab before the first wraps to the last.
6. **Filled fields persist as anchors.** Once dictated over, a field's
   brackets are gone and its text is teal, but the *position* is
   remembered. Ctrl+Tab still walks past it (and onto it again on a
   later cycle); Ctrl+Shift+Tab can return to it. Re-dictating selects
   the full filled range and replaces it. This is a deliberate UX
   improvement over PowerScribe, which loses filled fields entirely.
7. **No fields → Ctrl+Tab is a silent no-op.** No status flash, no
   inserted character.
8. **Mid-recording Ctrl+Tab** is dropped (editor is already read-only;
   we additionally suppress the navigation event to avoid yanking the
   selection during the streaming partial state machine).

## Scope of this slice

1. **`src/ui/field_navigator.py` (new)** — single file containing four
   small pieces:
   - `FieldAnchor` (dataclass): `id: str` (uuid, stable across edits),
     `default: str` (original placeholder text), `state: Literal["unfilled", "filled"]`.
   - `FieldRegistry`: owns the anchor list. Updates anchor positions on
     `editor.document().contentsChange`. Provides `find_next(cursor_pos)` /
     `find_prev(cursor_pos)` that return `Optional[FieldAnchor]`,
     wrapping at the document ends.
   - `FieldHighlighter(QSyntaxHighlighter)`: paints the pill format on
     unfilled-anchor regions (brackets color-matched to pill background;
     inner text dark-on-lavender) and the teal color on filled-anchor
     regions. Reads the registry's anchor list to know which ranges are
     anchors and what state each is in.
   - `FieldNavigator(QObject)`: installs an event filter on
     `MainWindow.editor`. On Ctrl+Tab / Ctrl+Shift+Tab, queries the
     registry, builds a `QTextCursor` covering the target anchor's
     full range, and assigns it to the editor.
2. **`src/main.py` wiring** — one new helper `_wire_field_navigator(window)`
   matching the existing `_wire_*` pattern. Constructs the registry,
   highlighter, and navigator; attaches them to `window.editor`.
3. **`MainWindow`** — exposes `editor` (already public); no new methods.
   The navigator/registry/highlighter all attach via `window.editor`
   without further mutation of `MainWindow`.

## Architecture

```
src/ui/field_navigator.py            (new, ~200 lines)
├── FieldAnchor (dataclass, mutable)
│   ├── id: str           # uuid, stable across edits
│   ├── default: str      # original placeholder text
│   ├── state: Literal["unfilled", "filled"]
│   ├── start: int        # current position in editor
│   └── end: int
├── FieldRegistry
│   ├── __init__(editor: QTextEdit)
│   ├── anchors() -> list[FieldAnchor]
│   ├── find_next(pos) -> Optional[FieldAnchor]
│   ├── find_prev(pos) -> Optional[FieldAnchor]
│   └── (listens to editor.document().contentsChange → update positions)
├── FieldHighlighter(QSyntaxHighlighter)
│   └── highlightBlock(text)
└── FieldNavigator(QObject)
    ├── eventFilter(obj, event)  # captures Ctrl+(Shift+)Tab on editor
    ├── jump_next()
    └── jump_prev()

src/main.py                          (extend)
└── _wire_field_navigator(window) -> None
```

The four classes ship in a single file because they're tightly
coupled and small. If any one grows past ~120 lines, split into a
`fields/` package.

## Anchor identity & position tracking

Each `FieldAnchor` has a UUID generated when first created. Position
`(start, end)` is tracked in the registry's side-table. Updates happen
on the document's `contentsChange(position, chars_removed, chars_added)`
signal — the most reliable Qt mechanism for observing every edit and
its byte-range, regardless of which cursor or format applied it. (We
deliberately do NOT use a `QTextCharFormat` custom property, because
the dictation pipeline replaces a selected field with `_dictation_format`
text — a different format than the field's — so any property attached
to the original bracketed range would not carry across the replace.)

Position-update rules per `contentsChange` event:

| Edit relative to anchor `[s, e]` | Result |
|---|---|
| Edit fully before anchor (`pos + chars_removed ≤ s`) | `s += delta`, `e += delta` |
| Edit fully after anchor (`pos ≥ e`) | no change |
| Edit fully inside anchor (`s ≤ pos`, `pos + chars_removed ≤ e`) | `e += delta` |
| Edit fully covers anchor (`pos ≤ s`, `pos + chars_removed ≥ e`), `chars_added > 0` | new range = `[pos, pos + chars_added]` |
| Edit fully covers anchor, `chars_added == 0` | collapse to `[pos, pos]`, mark "pending replace" — kept for one cycle in case dictation insert follows |
| Edit overlaps anchor's start or end | clamp anchor to the intersection of the new edit's range and the anchor's prior range |

(`delta = chars_added − chars_removed`.)

After updating positions, recompute state for each anchor: if the
text at `[start, end]` matches `\[(.+?)\]` exactly → `state = unfilled`,
`default = match.group(1)`. Otherwise → `state = filled`.

Cleanup pass before each Ctrl+Tab traversal: drop any anchor with
`start == end` that didn't get extended by a follow-up insert (e.g.,
the user deleted a field outright with no replacement).

The `dictation-replace` flow exercises this cleanly: a single record
session produces (1) a remove that fully covers the field's range
(collapses anchor to `[pos, pos]`, pending replace), then (2) one or
more inserts at `pos` (each one growing the anchor's `end`). At
session end the anchor's range = full dictated text, state = filled.

## Visual style — pill formatting

QSS classes on `MainWindow` already provide the Catppuccin palette.
The pill format uses these colors:

| Property | Value | Source |
|---|---|---|
| Pill background (unfilled) | `#b4befe` (lavender) | Catppuccin Lavender |
| Inner text color | `#1e1e2e` (base) | Catppuccin Base, for contrast on lavender |
| Bracket character color | `#b4befe` (matches background) | invisible-by-color |
| Active outline (cursor inside) | `#f9e2af` (yellow) | Catppuccin Yellow, distinct from record-pink |
| Filled-field color | `#94e2d5` (teal) | existing `MainWindow.DICTATION_COLOR` |

Active-vs-idle distinction is detected by checking whether the editor's
cursor position falls inside the anchor range; the highlighter applies
the outline format on rehighlight when an anchor is active.

**Filled-field color is applied by the highlighter, not inherited.**
Filled-anchor ranges get teal painted by the highlighter regardless
of how the text got there — dictation, manual typing, paste. This
keeps "what's in a field" visually consistent. (The dictation
controller's `_dictation_format` is what colors *non-anchored*
dictated prose teal; inside an anchor, the highlighter's teal wins.)

**Bracket characters occupy width.** Color-matched-to-background makes
them visually invisible but they still take up one character cell each.
The pill ends up about 2 cells wider than the inner text. This is a
known cosmetic quirk we accept for v1 — fixing it would require a
custom QTextObject (overkill).

## Data flow

### 1. Bracket text appears

Path: user types or pastes text containing `[…]`, or a future template
loader inserts it.

1. `document.contentsChange(pos, removed, added)` fires.
2. `FieldRegistry` updates existing anchor positions per the rules in
   "Anchor identity & position tracking".
3. `FieldRegistry` scans the changed region for new `\[([^\[\]]+)\]`
   matches that don't yet correspond to a known anchor. For each, mints
   a UUID and adds a `FieldAnchor(id=uuid, default=match.group(1),
   state="unfilled")` with positions from the match.
4. `FieldHighlighter.highlightBlock` re-runs (Qt fires this after the
   document change). It reads the registry to find which ranges are
   anchors, applies pill formatting to unfilled ones (3 sub-ranges per
   anchor: `[`, inner text, `]`) and the teal color to filled ones.

### 2. Ctrl+Tab pressed (in the editor)

1. Event filter on `editor` catches `QKeyEvent` with `Qt.Key_Tab` and
   `Qt.ControlModifier` (or `Qt.ControlModifier | Qt.ShiftModifier`).
2. Mid-recording guard: if `window._recording`, swallow the event and
   return. (The editor is already read-only, but we suppress the
   navigation outright to keep the streaming state machine clean.)
3. Read `editor.textCursor().position()`.
4. `FieldRegistry.find_next(pos)` returns the first anchor whose
   `start > pos`, wrapping to the first anchor if none match. Returns
   `None` only if there are zero anchors.
5. If `None`: silent no-op, return.
6. Else: build a `QTextCursor` with `setPosition(anchor.start)` then
   `setPosition(anchor.end, KeepAnchor)`; assign with
   `editor.setTextCursor(cursor)`. The whole field range — brackets
   included for unfilled, dictated text for filled — is now selected.
7. Trigger a rehighlight on the affected blocks so the active-outline
   format updates.

Ctrl+Shift+Tab is the same with `find_prev`.

### 3. Dictation replaces a selected field

1. User presses Record (F4 / button / HID) with a field selected.
2. `handle_trigger(True)` → `window.begin_streaming()` →
   `TextStreamingController.begin()`.
3. `begin()` already removes the active selection (see
   `text_streaming_controller.py:76-79`). `contentsChange` fires:
   `pos = anchor.start`, `chars_removed = anchor.end − anchor.start`,
   `chars_added = 0`. Per the rules, the anchor collapses to
   `[anchor.start, anchor.start]` and is marked pending replace.
4. Streaming partials and commits insert dictated text at the
   collapsed position with the teal `_dictation_format`.
5. Each insert fires `contentsChange` with `chars_added > 0` at
   `pos == anchor.start`. The "edit fully inside anchor" rule (or its
   collapsed-anchor equivalent) extends `anchor.end` by `chars_added`.
6. After streaming finishes, the anchor spans the full dictated text.
   State recomputes: text doesn't match the bracket regex → `filled`.
7. Highlighter rerun: the anchor no longer gets the pill; the
   `_dictation_format` provides the teal color. (The highlighter
   leaves filled-anchor ranges alone — its only job there is to NOT
   paint the pill.)
8. Anchor remains in the list. Ctrl+Tab at a later moment walks
   through it normally.

### 4. Re-dictating into a filled field

1. User Ctrl+Tabs onto a filled anchor. Selection covers its current
   text (e.g., "atrophic").
2. Record → dictation → exact same flow as #3. The anchor's range
   is replaced with the new dictation; state stays "filled"; end
   position updates.

## Error handling & edge cases

- **No fields in document, Ctrl+Tab pressed:** silent no-op.
- **Cursor inside a field's range, Ctrl+Tab pressed:** moves to the
  *next* field after the current one (current is the cursor's home,
  not a destination). Ctrl+Shift+Tab moves to the previous one.
- **Cursor past the last field:** wrap to first.
- **Malformed `[unclosed`:** regex never matches it; never anchored.
- **Empty `[]`:** regex requires `[^\[\]]+` (≥ 1 inner char) — rejected.
- **Adjacent fields `[a][b]`:** two separate anchors, walked in order.
- **User manually edits text inside a filled field:** the "edit fully
  inside anchor" rule extends/shrinks the anchor's `end`; future
  re-dictation still works.
- **User selects + deletes a field's whole range:** anchor collapses to
  `(pos, pos)` and is dropped on the next traversal cleanup pass.
- **Plain Tab pressed:** event filter only catches Ctrl-modified Tab;
  plain Tab falls through to QTextEdit and inserts `\t`.
- **Ctrl+Tab pressed when editor doesn't have focus:** event filter
  is scoped to `editor`; not intercepted elsewhere. Buttons handle
  Tab focus traversal as today.
- **`textChanged` storm during streaming:** highlighter runs per-block,
  not per-keystroke; the regex is cheap. Profiling pass will verify.
- **User pastes a 200-line template with 30 fields:** registry seeds
  all 30 anchors on the single `textChanged`. Linear in document size.

## Back-compatibility

Strictly additive. Nothing is removed; nothing's interface changes.

- `MainWindow` gains no new methods. The navigator/registry/highlighter
  attach via the existing `editor` reference.
- `TextStreamingController` is unmodified — its existing
  remove-selection-first behavior in `begin()` is reused as-is.
- `_dictation_format` is unchanged; filled fields inherit teal from it.
- `_build_stt_client`, orchestrator, recorder, hotkey, LLM workers all
  untouched.

## Testing

### Unit — `tests/unit/test_field_navigator.py` (new)

Most tests use `pytest-qt`'s `qtbot` to drive a real `QTextEdit`.

- **Regex coverage:** matches `[a]`, `[long phrase]`, `[a-b/c]`;
  rejects `[]`, `[`, `[unclosed`, `nested [outer [inner] outer]`.
- **Registry seeding:** typing a string with 3 bracket fields creates
  3 anchors in document order with correct `default` values.
- **`find_next`/`find_prev`:** at cursor-before-all, between, after-all,
  inside-an-anchor — verify wrap-around and "current is not a target."
- **Ctrl+Tab via `QTest.keyClick`:** selects the first unfilled
  anchor's full range (brackets included).
- **Ctrl+Shift+Tab:** walks backwards including wrap.
- **Plain Tab regression guard:** inserts `\t`, does NOT navigate.
- **Highlighter:** pill format applied on unfilled (3 sub-ranges per
  anchor: opening bracket invisible, inner text dark-on-lavender,
  closing bracket invisible), teal applied on filled anchor ranges.
- **Dictation-replace flow** (using a stub STT that returns a fixed
  string): with a field selected, drive `begin_streaming()` →
  `commit_partial("atrophic")`. After: anchor `state == "filled"`,
  bracket-free, end position matches new text length.
- **Re-dictate filled field:** select via Ctrl+Tab, dictate again,
  text replaces, anchor stays "filled" with new end position.
- **Empty document + Ctrl+Tab:** no exceptions, no selection change.
- **Mid-recording Ctrl+Tab:** with `window._recording = True`, Ctrl+Tab
  is dropped — selection unchanged.
- **Manual full-range delete:** select anchor, delete, confirm anchor
  removed from registry.

### Manual smoke test

1. Launch `python -m src.main`.
2. Paste: `The pancreas is [normal] without [acute] findings. The kidneys are [size].`
3. Confirm three lavender pills, brackets read invisibly, three
   default texts ("normal", "acute", "size") visible inside each.
4. Ctrl+Tab — first pill selected with yellow outline. Press Record,
   say "atrophic", press Stop. Field becomes teal "atrophic", no pill.
5. Ctrl+Tab twice — confirm next stop is `[size]` (skips the now-filled
   field on first jump, lands on the third anchor; second Ctrl+Tab
   would wrap to "atrophic" or to `[acute]` depending on order — note
   the cycle for a docstring example).
6. Ctrl+Shift+Tab — walks back, lands on the filled "atrophic" field.
   Confirm the whole word is selected.
7. Press Tab (no Ctrl) — confirm a tab character is inserted.
8. Press Record → Ctrl+Tab during recording → confirm selection
   unchanged.

## Profiling pass (final plan step)

The highlighter runs on every `textChanged` and re-regexes affected
blocks. For a long report (≥ 200 lines), this could matter. Add a
profiling scenario that:

- Loads a 200-line stub template with 30 fields.
- Measures `textChanged → highlightBlock complete` wall time.
- Measures `Ctrl+Tab → selection updated` wall time across cursor
  positions (best/median/worst case).

Acceptable thresholds: highlighter < 5 ms per textChanged on the test
machine; Ctrl+Tab dispatch < 2 ms.

If exceeded, the likely fix is to skip highlighter work for blocks
that haven't changed (per-block dirty bit) — well-trodden territory.

## Dead-code + readability sweep (final plan step)

- Re-read `field_navigator.py` end-to-end. Each class < 60 lines, each
  method < 20 lines, target. Split if over.
- Re-read `_wire_field_navigator` in `main.py`; confirm it follows the
  shape of the other `_wire_*` helpers.
- Grep for any TODOs / FIXMEs introduced during implementation;
  resolve or hoist into the next slice.
- Confirm no `print()` debug calls leaked into production paths.

## Slice boundary

The slice ends at: user can paste a template with brackets, navigate
between fields with Ctrl+Tab, dictate to replace a field, navigate
back to filled fields and re-dictate. Profiling and refactor passes
done. Tests green. Manual smoke test confirms PowerScribe-feel.

Natural next slices (NOT in scope here):
- "Insert template" button + a small library of hard-coded sample
  templates.
- Pick-list field type (dropdown when Ctrl+Tab lands on it).
- Voice command "next field" / "field {name}".
- Sign-time guardrail that blocks signing while unfilled fields remain.
- Hotkey remap layer + SpeechMic button binding.
