# Field Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect `[default]` bracket fields in the editor, highlight them as lavender pills, and let the user navigate with Ctrl+Tab / Ctrl+Shift+Tab. Selection-on-Tab combined with the existing `TextStreamingController.begin()` removes-selection behavior gives PowerScribe-style dictate-to-replace. Filled fields persist as navigable anchors (improvement over PowerScribe).

**Architecture:** One new module `src/ui/field_navigator.py` containing four small pieces: a `FieldAnchor` dataclass, a `FieldRegistry` that tracks anchors via `QTextDocument.contentsChange`, a `FieldHighlighter(QSyntaxHighlighter)` that paints pills (unfilled) and teal (filled), and a `FieldNavigator(QObject)` that installs an event filter on the editor to handle Ctrl-modified Tab keys. A new `_wire_field_navigator(window)` helper in `main.py` matches the existing `_wire_*` pattern.

**Tech Stack:** PyQt6 (QTextEdit, QSyntaxHighlighter, QTextCharFormat, QTextDocument), pytest, pytest-qt (`qtbot` fixture).

**Spec:** [`docs/superpowers/specs/2026-04-26-field-navigation-design.md`](../specs/2026-04-26-field-navigation-design.md)

---

## File Structure

| Path | Status | Responsibility |
|---|---|---|
| `src/ui/field_navigator.py` | **new** (~250 lines) | All four classes + module-level helpers |
| `tests/unit/test_field_navigator.py` | **new** (~400 lines) | Unit + qtbot tests for every behavior |
| `src/main.py` | **modify** | Add `_wire_field_navigator` helper; call from `main()` |

Single-file module is intentional — the four classes are tightly coupled. If any class grows past ~120 lines during implementation, split into a `src/ui/fields/` package then.

---

## Task 1: Module skeleton with `FieldAnchor` dataclass

**Files:**
- Create: `src/ui/field_navigator.py`
- Test: `tests/unit/test_field_navigator.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_field_navigator.py
from src.ui.field_navigator import FieldAnchor


def test_field_anchor_construction():
    """FieldAnchor is a mutable dataclass with id, default, state, start, end."""
    a = FieldAnchor(id="abc", default="normal", state="unfilled", start=10, end=18)
    assert a.id == "abc"
    assert a.default == "normal"
    assert a.state == "unfilled"
    assert a.start == 10
    assert a.end == 18
    # Mutable — we update positions in place
    a.end = 25
    assert a.end == 25
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.ui.field_navigator'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ui/field_navigator.py
"""Field detection, highlighting, and Ctrl+Tab navigation for the
dictation editor.

A "field" is a `[default text]` placeholder in the editor. The user
navigates between fields with Ctrl+Tab / Ctrl+Shift+Tab; dictation
replaces the active field. Filled fields persist as navigable anchors
so the user can jump back and re-dictate.

See docs/superpowers/specs/2026-04-26-field-navigation-design.md for
the full design and decision log.
"""
from dataclasses import dataclass
from typing import Literal


@dataclass
class FieldAnchor:
    """One field's stable identity and current span.

    `id` is a UUID minted when the anchor is first created and never
    changes — that's how we track a field across edits even after its
    bracketed default is replaced by dictated text.

    `start` and `end` are mutable; the registry updates them on every
    document change.
    """
    id: str
    default: str
    state: Literal["unfilled", "filled"]
    start: int
    end: int
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ui/field_navigator.py tests/unit/test_field_navigator.py
git commit -m "feat(fields): FieldAnchor dataclass scaffold"
```

---

## Task 2: Bracket regex helper

**Files:**
- Modify: `src/ui/field_navigator.py`
- Test: `tests/unit/test_field_navigator.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_field_navigator.py`:

```python
from src.ui.field_navigator import find_brackets


def test_find_brackets_single_match():
    """Returns one (start, end, default) tuple for a single bracketed field."""
    result = find_brackets("Hello [world] there")
    assert result == [(6, 13, "world")]


def test_find_brackets_multiple_matches():
    """Returns matches in document order."""
    result = find_brackets("[a] middle [longer phrase] end")
    assert result == [(0, 3, "a"), (11, 26, "longer phrase")]


def test_find_brackets_rejects_empty():
    """`[]` requires at least one inner char — rejected."""
    assert find_brackets("[]") == []


def test_find_brackets_rejects_unclosed():
    """`[unclosed` never matches."""
    assert find_brackets("[unclosed text") == []


def test_find_brackets_innermost_only():
    """Nested brackets: regex matches the innermost closed pair only."""
    result = find_brackets("[outer [inner] outer]")
    # Inner [inner] matches; outer brackets are bare punctuation
    assert result == [(7, 14, "inner")]


def test_find_brackets_adjacent():
    """`[a][b]` returns two anchors."""
    assert find_brackets("[a][b]") == [(0, 3, "a"), (3, 6, "b")]


def test_find_brackets_empty_string():
    assert find_brackets("") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: FAIL — `cannot import name 'find_brackets'`.

- [ ] **Step 3: Implement `find_brackets`**

Append to `src/ui/field_navigator.py`:

```python
import re

# Match `[content]` where content is one-or-more chars excluding `[` and `]`.
# This is greedy within the inner-char class, so empty brackets and unclosed
# brackets fail; nested brackets resolve to the innermost closed pair.
_FIELD_PATTERN = re.compile(r"\[([^\[\]]+)\]")


def find_brackets(text: str) -> list[tuple[int, int, str]]:
    """Return `(start, end, default)` for every bracketed field in `text`.

    `start` is the position of the opening `[`; `end` is one past the
    closing `]` (the standard half-open Python range). `default` is the
    text between the brackets — used as the field's placeholder/default.
    """
    return [(m.start(), m.end(), m.group(1)) for m in _FIELD_PATTERN.finditer(text)]
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: PASS — 8 tests.

- [ ] **Step 5: Commit**

```bash
git add src/ui/field_navigator.py tests/unit/test_field_navigator.py
git commit -m "feat(fields): bracket detection regex"
```

---

## Task 3: Position-update rules (pure function)

**Files:**
- Modify: `src/ui/field_navigator.py`
- Test: `tests/unit/test_field_navigator.py`

This task implements the `contentsChange` rules from the spec as a pure function over a `FieldAnchor`, so the rules are unit-testable without a Qt event loop.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_field_navigator.py`:

```python
from src.ui.field_navigator import update_anchor_position


def _anchor(start: int, end: int) -> FieldAnchor:
    return FieldAnchor(id="t", default="x", state="unfilled", start=start, end=end)


def test_update_edit_fully_before_anchor_shifts_both():
    """Edit before anchor: both start and end shift by delta."""
    a = _anchor(20, 28)
    update_anchor_position(a, pos=5, removed=2, added=5)  # delta = +3
    assert (a.start, a.end) == (23, 31)


def test_update_edit_fully_after_anchor_no_change():
    """Edit after anchor: positions untouched."""
    a = _anchor(10, 18)
    update_anchor_position(a, pos=20, removed=2, added=5)
    assert (a.start, a.end) == (10, 18)


def test_update_edit_fully_inside_anchor_extends_end():
    """Edit fully inside the anchor's range: end shifts by delta, start fixed."""
    a = _anchor(10, 18)
    update_anchor_position(a, pos=12, removed=1, added=4)  # delta = +3
    assert (a.start, a.end) == (10, 21)


def test_update_edit_fully_covers_anchor_replaces_with_added():
    """Edit covers the whole anchor with a non-empty replacement: anchor becomes [pos, pos + added]."""
    a = _anchor(10, 18)
    update_anchor_position(a, pos=10, removed=8, added=5)  # replace 8 chars with 5
    assert (a.start, a.end) == (10, 15)


def test_update_edit_fully_covers_anchor_with_zero_added_collapses():
    """Edit removes the whole anchor with no replacement: collapse to (pos, pos)."""
    a = _anchor(10, 18)
    update_anchor_position(a, pos=10, removed=8, added=0)
    assert (a.start, a.end) == (10, 10)


def test_update_edit_overlaps_anchor_start():
    """Edit starts before anchor and ends inside: clamp start to pos+added, end shifts by delta."""
    a = _anchor(10, 20)
    update_anchor_position(a, pos=8, removed=4, added=2)  # spans [8, 12], anchor was [10, 20]
    # start clamps to insertion endpoint (8+2=10); end shifts by delta -2 → 18
    assert (a.start, a.end) == (10, 18)


def test_update_edit_overlaps_anchor_end_with_insert():
    """Edit starts inside anchor and ends past it: end clamps to insertion endpoint
    (anchor absorbs any inserted text in the overlap region)."""
    a = _anchor(10, 20)
    update_anchor_position(a, pos=15, removed=10, added=2)  # spans [15, 25]
    # End clamps to pos+added = 17; start unchanged
    assert (a.start, a.end) == (10, 17)


def test_update_edit_overlaps_anchor_end_pure_delete():
    """Pure deletion overlapping anchor's end: end clamps to deletion start."""
    a = _anchor(10, 20)
    update_anchor_position(a, pos=15, removed=10, added=0)  # spans [15, 25]
    # pos + added = 15 — end clamps there
    assert (a.start, a.end) == (10, 15)


def test_update_collapsed_anchor_grows_on_insert_at_position():
    """Collapsed (pos, pos) anchor grows when text inserts at pos.

    This is the load-bearing case for the dictation-replace flow: after
    `removeSelectedText`, the anchor is collapsed at the position; subsequent
    `insertText` should grow the anchor to cover the new text rather than
    pushing it forward.
    """
    a = _anchor(10, 10)  # already collapsed
    update_anchor_position(a, pos=10, removed=0, added=8)
    assert (a.start, a.end) == (10, 18)


def test_update_edit_at_anchor_start_with_no_collapse():
    """Insert at a non-collapsed anchor's start position: insert goes BEFORE anchor.

    This is Qt's standard convention: an insert at position N pushes content
    originally at N to N+added. Only collapsed anchors absorb the insert.
    """
    a = _anchor(10, 18)
    update_anchor_position(a, pos=10, removed=0, added=5)
    assert (a.start, a.end) == (15, 23)


def test_update_insert_at_anchor_end_grows_anchor():
    """Streaming dictation flow: subsequent inserts at the (currently filling)
    anchor's end position should grow the anchor.

    During dictation streaming, after the field is removed and the first
    partial inserted, the anchor is non-collapsed (e.g., 10..15 covering
    'hello'). Each subsequent partial inserts at the end (pos=15). The
    anchor must grow to absorb that text.
    """
    a = _anchor(10, 15)
    update_anchor_position(a, pos=15, removed=0, added=1)  # insert at end
    assert (a.start, a.end) == (10, 16)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: FAIL — `cannot import name 'update_anchor_position'`.

- [ ] **Step 3: Implement `update_anchor_position`**

Append to `src/ui/field_navigator.py`:

```python
def update_anchor_position(anchor: FieldAnchor, pos: int, removed: int, added: int) -> None:
    """Apply one `contentsChange` event to an anchor in place.

    Treats `anchor.start` like a "keep position on insert" cursor (insert
    at a non-collapsed anchor's start does NOT push start forward — that
    insert is conceptually before the anchor) and `anchor.end` like a
    default cursor (insert at end pushes end forward).

    The dictation-replace flow specifically depends on the collapsed-anchor
    case (start == end): an insert at the collapsed position grows the
    anchor to absorb the inserted text. This is what the "fully covers"
    branch handles when start == end == pos and removed == 0.
    """
    delta = added - removed
    change_end = pos + removed
    s, e = anchor.start, anchor.end

    # Edit fully covers anchor: anchor becomes [pos, pos + added].
    # When chars_added == 0 this collapses the anchor; when chars_added > 0
    # the anchor "becomes" the inserted text. Collapsed-anchor + insert at
    # position is also caught here (s == e and pos == s, so pos <= s and
    # change_end == pos == s == e ≥ e is satisfied).
    if pos <= s and change_end >= e:
        anchor.start = pos
        anchor.end = pos + added
        return

    # Update start: an insert AT a non-collapsed anchor's start goes before
    # the anchor (Qt's standard convention); collapsed-anchor inserts at
    # start are already handled by the "fully covers" branch above.
    if change_end <= s:
        if pos < s:
            anchor.start = s + delta
        elif pos == s and removed == 0 and added > 0:
            anchor.start = s + added
    elif pos < s:
        # Edit starts before anchor and ends inside.
        anchor.start = pos + added

    # Update end: an insert AT the anchor's end goes INSIDE the anchor —
    # this is what makes streaming dictation grow the anchor as each
    # partial lands at the previous partial's end position.
    if pos > e:
        return  # edit fully after anchor
    if pos == e:
        anchor.end = e + added
    elif change_end <= e:
        anchor.end = e + delta
    else:
        # Edit overlaps anchor's end — clamp to insertion endpoint.
        anchor.end = pos + added
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: PASS — all tests green (16 total now).

- [ ] **Step 5: Commit**

```bash
git add src/ui/field_navigator.py tests/unit/test_field_navigator.py
git commit -m "feat(fields): contentsChange position-update rules"
```

---

## Task 4: `FieldRegistry` — initial seeding from editor text

**Files:**
- Modify: `src/ui/field_navigator.py`
- Test: `tests/unit/test_field_navigator.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_field_navigator.py`:

```python
from PyQt6.QtWidgets import QTextEdit
from src.ui.field_navigator import FieldRegistry


def test_registry_seeds_from_existing_text(qtbot):
    """Constructing a FieldRegistry on an editor with bracketed text creates one anchor per field, in document order."""
    editor = QTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("The pancreas is [normal] and the liver shows [size] disease.")

    registry = FieldRegistry(editor)

    anchors = registry.anchors()
    assert len(anchors) == 2
    assert (anchors[0].start, anchors[0].end, anchors[0].default) == (16, 24, "normal")
    assert (anchors[1].start, anchors[1].end, anchors[1].default) == (45, 51, "size")
    assert all(a.state == "unfilled" for a in anchors)
    assert all(a.id for a in anchors)  # non-empty UUIDs
    assert anchors[0].id != anchors[1].id  # unique


def test_registry_empty_editor_has_no_anchors(qtbot):
    editor = QTextEdit()
    qtbot.addWidget(editor)
    registry = FieldRegistry(editor)
    assert registry.anchors() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: FAIL — `cannot import name 'FieldRegistry'`.

- [ ] **Step 3: Implement `FieldRegistry` seeding**

Add to `src/ui/field_navigator.py`:

```python
import uuid
from PyQt6.QtWidgets import QTextEdit


class FieldRegistry:
    """Owns the list of FieldAnchors and keeps their positions in sync with
    the editor.

    Anchors live as long as their text is in the document. Positions update
    on every `contentsChange` from the underlying QTextDocument; state
    (`unfilled` vs `filled`) is recomputed by re-checking whether the text
    at each anchor's current range still matches the bracket regex.
    """

    def __init__(self, editor: QTextEdit):
        self._editor = editor
        self._anchors: list[FieldAnchor] = []
        self._seed_from_text()

    def anchors(self) -> list[FieldAnchor]:
        """Anchors in document order. Returns the live list — callers must
        not mutate it."""
        return self._anchors

    def _seed_from_text(self) -> None:
        text = self._editor.toPlainText()
        for start, end, default in find_brackets(text):
            self._anchors.append(
                FieldAnchor(
                    id=str(uuid.uuid4()),
                    default=default,
                    state="unfilled",
                    start=start,
                    end=end,
                )
            )
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: PASS — 18 tests.

- [ ] **Step 5: Commit**

```bash
git add src/ui/field_navigator.py tests/unit/test_field_navigator.py
git commit -m "feat(fields): FieldRegistry initial seeding"
```

---

## Task 5: `FieldRegistry` — `contentsChange` listener

**Files:**
- Modify: `src/ui/field_navigator.py`
- Test: `tests/unit/test_field_navigator.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_field_navigator.py`:

```python
def test_registry_updates_positions_on_insert_before(qtbot):
    """Inserting text before a field shifts its positions."""
    editor = QTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("[a] tail")  # field at [0, 3]

    registry = FieldRegistry(editor)
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.insertText("XX")  # insert 2 chars at pos 0

    anchors = registry.anchors()
    assert (anchors[0].start, anchors[0].end) == (2, 5)


def test_registry_drops_zombie_anchor_after_full_delete(qtbot):
    """Deleting a field's whole range drops the anchor (after cleanup)."""
    editor = QTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("Pre [a] post")  # field at [4, 7]

    registry = FieldRegistry(editor)
    assert len(registry.anchors()) == 1

    # Select and delete the field's range
    cursor = editor.textCursor()
    cursor.setPosition(4)
    cursor.setPosition(7, cursor.MoveMode.KeepAnchor)
    cursor.removeSelectedText()

    # An immediate read still shows the collapsed anchor (pending replace);
    # cleanup happens on next traversal
    registry.cleanup_zombies()
    assert registry.anchors() == []


def test_registry_marks_filled_after_replace(qtbot):
    """When a field's range is replaced with non-bracket text, anchor flips to filled."""
    editor = QTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("[normal]")

    registry = FieldRegistry(editor)
    assert registry.anchors()[0].state == "unfilled"

    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(8, cursor.MoveMode.KeepAnchor)
    cursor.removeSelectedText()
    cursor.insertText("atrophic")

    anchors = registry.anchors()
    assert len(anchors) == 1
    assert anchors[0].state == "filled"
    assert (anchors[0].start, anchors[0].end) == (0, 8)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: FAIL — `AttributeError: 'FieldRegistry' object has no attribute 'cleanup_zombies'` (and position tests fail because we don't yet listen to changes).

- [ ] **Step 3: Implement `contentsChange` listener and state recompute**

In `src/ui/field_navigator.py`, modify `FieldRegistry.__init__` and add new methods:

```python
class FieldRegistry:
    def __init__(self, editor: QTextEdit):
        self._editor = editor
        self._anchors: list[FieldAnchor] = []
        self._seed_from_text()
        editor.document().contentsChange.connect(self._on_contents_change)

    def anchors(self) -> list[FieldAnchor]:
        return self._anchors

    def cleanup_zombies(self) -> None:
        """Drop anchors whose range collapsed and never got refilled.

        Called before each Ctrl+Tab traversal so a deleted-with-no-replacement
        field doesn't linger as a zero-length zombie.
        """
        self._anchors = [a for a in self._anchors if a.end > a.start]

    def _seed_from_text(self) -> None:
        text = self._editor.toPlainText()
        for start, end, default in find_brackets(text):
            self._anchors.append(
                FieldAnchor(
                    id=str(uuid.uuid4()),
                    default=default,
                    state="unfilled",
                    start=start,
                    end=end,
                )
            )

    def _on_contents_change(self, position: int, removed: int, added: int) -> None:
        """Update every anchor's position via the rules in update_anchor_position,
        then recompute filled/unfilled state from the current text, then add any
        newly-bracketed regions as new anchors."""
        for anchor in self._anchors:
            update_anchor_position(anchor, position, removed, added)
        self._recompute_states()
        self._adopt_new_brackets()

    def _recompute_states(self) -> None:
        """Set state = 'unfilled' if anchor's text matches the bracket regex,
        else 'filled'."""
        text = self._editor.toPlainText()
        for anchor in self._anchors:
            span = text[anchor.start:anchor.end]
            m = _FIELD_PATTERN.fullmatch(span)
            if m is not None:
                anchor.state = "unfilled"
                anchor.default = m.group(1)
            else:
                anchor.state = "filled"

    def _adopt_new_brackets(self) -> None:
        """Find bracket matches that don't correspond to any existing anchor
        and add them as new ones. Avoids creating duplicates for unfilled
        anchors that already exist at a given position.

        Two anchors at the same start position are treated as the same field
        — this is how an unfilled anchor created at seed time gets re-found
        after edits without growing duplicates.
        """
        existing_starts = {a.start for a in self._anchors if a.state == "unfilled"}
        text = self._editor.toPlainText()
        for start, end, default in find_brackets(text):
            if start in existing_starts:
                continue
            self._anchors.append(
                FieldAnchor(
                    id=str(uuid.uuid4()),
                    default=default,
                    state="unfilled",
                    start=start,
                    end=end,
                )
            )
        self._anchors.sort(key=lambda a: a.start)
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: PASS — 21 tests.

- [ ] **Step 5: Commit**

```bash
git add src/ui/field_navigator.py tests/unit/test_field_navigator.py
git commit -m "feat(fields): contentsChange listener + state recompute"
```

---

## Task 6: `FieldRegistry` — `find_next` / `find_prev` with wrap

**Files:**
- Modify: `src/ui/field_navigator.py`
- Test: `tests/unit/test_field_navigator.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_field_navigator.py`:

```python
def test_find_next_returns_first_anchor_after_pos(qtbot):
    editor = QTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("zero [one] mid [two] end")  # fields at 5-10 and 15-20

    registry = FieldRegistry(editor)

    found = registry.find_next(0)
    assert found is not None and found.default == "one"

    found = registry.find_next(10)
    assert found is not None and found.default == "two"


def test_find_next_wraps_when_past_last(qtbot):
    editor = QTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("[a] tail [b]")  # anchors at 0-3 and 9-12

    registry = FieldRegistry(editor)

    # Past last: wrap to first
    found = registry.find_next(20)
    assert found is not None and found.default == "a"


def test_find_next_returns_none_when_no_anchors(qtbot):
    editor = QTextEdit()
    qtbot.addWidget(editor)
    registry = FieldRegistry(editor)
    assert registry.find_next(0) is None


def test_find_next_skips_anchor_when_cursor_is_inside_it(qtbot):
    """Per the spec: 'current is the cursor's home, not a destination.'"""
    editor = QTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("[one] mid [two]")  # 0-5 and 10-15

    registry = FieldRegistry(editor)

    # Cursor inside first anchor → next should be second
    found = registry.find_next(2)
    assert found is not None and found.default == "two"


def test_find_prev_returns_last_anchor_before_pos(qtbot):
    editor = QTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("[a] mid [b] end [c]")  # 0-3, 8-11, 16-19

    registry = FieldRegistry(editor)

    found = registry.find_prev(15)
    assert found is not None and found.default == "b"


def test_find_prev_wraps_when_before_first(qtbot):
    editor = QTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("[a] [b]")  # 0-3 and 4-7

    registry = FieldRegistry(editor)

    # Before first: wrap to last
    found = registry.find_prev(0)
    assert found is not None and found.default == "b"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: FAIL — `'FieldRegistry' object has no attribute 'find_next'`.

- [ ] **Step 3: Implement `find_next` and `find_prev`**

Append to `FieldRegistry` in `src/ui/field_navigator.py`:

```python
    def find_next(self, pos: int) -> "FieldAnchor | None":
        """Anchor with the smallest start strictly greater than `pos`.

        Wraps to the first anchor if none qualify and the list is non-empty.
        Returns None only when there are no anchors at all.
        """
        if not self._anchors:
            return None
        for a in self._anchors:
            if a.start > pos:
                return a
        return self._anchors[0]

    def find_prev(self, pos: int) -> "FieldAnchor | None":
        """Anchor with the largest end strictly less than `pos`.

        Wraps to the last anchor if none qualify and the list is non-empty.
        """
        if not self._anchors:
            return None
        for a in reversed(self._anchors):
            if a.end < pos:
                return a
        return self._anchors[-1]
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: PASS — 27 tests.

- [ ] **Step 5: Commit**

```bash
git add src/ui/field_navigator.py tests/unit/test_field_navigator.py
git commit -m "feat(fields): find_next / find_prev with wrap-around"
```

---

## Task 7: `FieldHighlighter` — pill on unfilled

**Files:**
- Modify: `src/ui/field_navigator.py`
- Test: `tests/unit/test_field_navigator.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_field_navigator.py`:

```python
from PyQt6.QtGui import QColor, QTextCursor
from src.ui.field_navigator import FieldHighlighter, PILL_BG, PILL_TEXT


def test_highlighter_paints_pill_on_unfilled(qtbot):
    """Bracketed text gets pill background and dark text on the inner chars; brackets get color-matched-to-bg foreground."""
    editor = QTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("[a]")

    registry = FieldRegistry(editor)
    highlighter = FieldHighlighter(editor.document(), registry)
    highlighter.rehighlight()  # force pass

    doc = editor.document()
    cursor = QTextCursor(doc)

    # Opening bracket at position 0
    cursor.setPosition(0)
    cursor.setPosition(1, cursor.MoveMode.KeepAnchor)
    fmt_open = cursor.charFormat()
    assert fmt_open.foreground().color() == QColor(PILL_BG)
    assert fmt_open.background().color() == QColor(PILL_BG)

    # Inner char at position 1
    cursor.setPosition(1)
    cursor.setPosition(2, cursor.MoveMode.KeepAnchor)
    fmt_inner = cursor.charFormat()
    assert fmt_inner.foreground().color() == QColor(PILL_TEXT)
    assert fmt_inner.background().color() == QColor(PILL_BG)

    # Closing bracket at position 2
    cursor.setPosition(2)
    cursor.setPosition(3, cursor.MoveMode.KeepAnchor)
    fmt_close = cursor.charFormat()
    assert fmt_close.foreground().color() == QColor(PILL_BG)
    assert fmt_close.background().color() == QColor(PILL_BG)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: FAIL — `cannot import name 'FieldHighlighter'`.

- [ ] **Step 3: Implement `FieldHighlighter` (unfilled-only for this task)**

Add to `src/ui/field_navigator.py`:

```python
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import QTextEdit  # already imported above; keep at top of file

# Catppuccin Lavender — pill background.
PILL_BG = "#b4befe"
# Catppuccin Base — dark text on lavender.
PILL_TEXT = "#1e1e2e"
# Catppuccin Yellow — outline on the active (cursor-inside) anchor. Reserved for Task 9.
ACTIVE_OUTLINE = "#f9e2af"
# Catppuccin Teal — already used for dictation. Filled fields wear this.
FILLED_TEXT = "#94e2d5"


class FieldHighlighter(QSyntaxHighlighter):
    """Paints field formatting based on the registry's anchor list.

    Unfilled anchors get the pill: lavender background across the entire
    range, with the bracket characters foreground'd to match the
    background (visually invisible, structurally present) and the inner
    text in dark base color.

    Filled anchors get the existing dictation-teal foreground (Task 8).
    """

    def __init__(self, document, registry: FieldRegistry):
        super().__init__(document)
        self._registry = registry

    def highlightBlock(self, text: str) -> None:
        block_start = self.currentBlock().position()
        block_end = block_start + len(text)
        for anchor in self._registry.anchors():
            # Skip anchors that don't intersect this block
            if anchor.end <= block_start or anchor.start >= block_end:
                continue
            local_start = max(0, anchor.start - block_start)
            local_end = min(len(text), anchor.end - block_start)
            if anchor.state == "unfilled":
                self._paint_pill(local_start, local_end)

    def _paint_pill(self, start: int, end: int) -> None:
        """Paint a 3-range pill: invisible bracket, dark inner text, invisible bracket."""
        if end - start < 2:  # need at least `[]`
            return
        bg = QColor(PILL_BG)
        bracket_fmt = QTextCharFormat()
        bracket_fmt.setForeground(bg)
        bracket_fmt.setBackground(bg)
        inner_fmt = QTextCharFormat()
        inner_fmt.setForeground(QColor(PILL_TEXT))
        inner_fmt.setBackground(bg)
        # Opening bracket
        self.setFormat(start, 1, bracket_fmt)
        # Inner text
        if end - start > 2:
            self.setFormat(start + 1, end - start - 2, inner_fmt)
        # Closing bracket
        self.setFormat(end - 1, 1, bracket_fmt)
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: PASS — 28 tests.

- [ ] **Step 5: Commit**

```bash
git add src/ui/field_navigator.py tests/unit/test_field_navigator.py
git commit -m "feat(fields): highlighter pill format on unfilled anchors"
```

---

## Task 8: `FieldHighlighter` — teal on filled

**Files:**
- Modify: `src/ui/field_navigator.py`
- Test: `tests/unit/test_field_navigator.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_field_navigator.py`:

```python
from src.ui.field_navigator import FILLED_TEXT


def test_highlighter_paints_teal_on_filled(qtbot):
    editor = QTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("[normal]")

    registry = FieldRegistry(editor)
    highlighter = FieldHighlighter(editor.document(), registry)

    # Replace the bracketed range with plain text → anchor flips to filled
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(8, cursor.MoveMode.KeepAnchor)
    cursor.removeSelectedText()
    cursor.insertText("atrophic")

    highlighter.rehighlight()

    # Anchor is now [0, 8] = "atrophic" — every char should be teal,
    # no pill background
    doc = editor.document()
    check = QTextCursor(doc)
    check.setPosition(0)
    check.setPosition(8, check.MoveMode.KeepAnchor)
    fmt = check.charFormat()
    assert fmt.foreground().color() == QColor(FILLED_TEXT)
    # No pill background: should be the default (transparent / not lavender)
    assert fmt.background().color() != QColor(PILL_BG)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: FAIL — filled anchors aren't being painted.

- [ ] **Step 3: Add filled branch to `highlightBlock`**

In `src/ui/field_navigator.py`, modify `FieldHighlighter.highlightBlock`:

```python
    def highlightBlock(self, text: str) -> None:
        block_start = self.currentBlock().position()
        block_end = block_start + len(text)
        for anchor in self._registry.anchors():
            if anchor.end <= block_start or anchor.start >= block_end:
                continue
            local_start = max(0, anchor.start - block_start)
            local_end = min(len(text), anchor.end - block_start)
            if anchor.state == "unfilled":
                self._paint_pill(local_start, local_end)
            else:
                self._paint_filled(local_start, local_end)

    def _paint_filled(self, start: int, end: int) -> None:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(FILLED_TEXT))
        self.setFormat(start, end - start, fmt)
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: PASS — 29 tests.

- [ ] **Step 5: Commit**

```bash
git add src/ui/field_navigator.py tests/unit/test_field_navigator.py
git commit -m "feat(fields): highlighter teal format on filled anchors"
```

---

## Task 9: `FieldHighlighter` — yellow outline on active

**Files:**
- Modify: `src/ui/field_navigator.py`
- Test: `tests/unit/test_field_navigator.py`

The "active" anchor is whichever one contains the editor's current cursor position. The outline is rendered as an underline-style stroke since `QTextCharFormat` does not natively support border-outline.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_field_navigator.py`:

```python
def test_highlighter_paints_outline_on_active_anchor(qtbot):
    editor = QTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("[a] [b]")  # 0-3 and 4-7

    registry = FieldRegistry(editor)
    highlighter = FieldHighlighter(editor.document(), registry)

    # Place cursor inside the second field
    cursor = editor.textCursor()
    cursor.setPosition(5)
    editor.setTextCursor(cursor)
    highlighter.rehighlight()

    # First anchor: pill, no underline
    doc = editor.document()
    check = QTextCursor(doc)
    check.setPosition(1)
    check.setPosition(2, check.MoveMode.KeepAnchor)
    fmt_first = check.charFormat()
    assert fmt_first.fontUnderline() is False or not fmt_first.fontUnderline()

    # Second anchor: pill + underline (yellow)
    check.setPosition(5)
    check.setPosition(6, check.MoveMode.KeepAnchor)
    fmt_second = check.charFormat()
    assert fmt_second.fontUnderline() is True
    assert fmt_second.underlineColor() == QColor(ACTIVE_OUTLINE)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: FAIL — no underline applied.

- [ ] **Step 3: Wire active-anchor detection into the highlighter**

Modify `src/ui/field_navigator.py`:

```python
class FieldHighlighter(QSyntaxHighlighter):
    def __init__(self, document, registry: FieldRegistry, editor: QTextEdit | None = None):
        super().__init__(document)
        self._registry = registry
        self._editor = editor  # used to read current cursor position; can be None for tests that don't care

    def highlightBlock(self, text: str) -> None:
        block_start = self.currentBlock().position()
        block_end = block_start + len(text)
        active_pos = self._editor.textCursor().position() if self._editor else -1
        for anchor in self._registry.anchors():
            if anchor.end <= block_start or anchor.start >= block_end:
                continue
            local_start = max(0, anchor.start - block_start)
            local_end = min(len(text), anchor.end - block_start)
            is_active = anchor.start <= active_pos <= anchor.end
            if anchor.state == "unfilled":
                self._paint_pill(local_start, local_end)
            else:
                self._paint_filled(local_start, local_end)
            if is_active:
                self._paint_active_outline(local_start, local_end)

    def _paint_active_outline(self, start: int, end: int) -> None:
        fmt = QTextCharFormat()
        fmt.setFontUnderline(True)
        fmt.setUnderlineColor(QColor(ACTIVE_OUTLINE))
        # Merge with existing format on this range so we don't blow away the pill.
        for offset in range(start, end):
            existing = self.format(offset)
            existing.setFontUnderline(True)
            existing.setUnderlineColor(QColor(ACTIVE_OUTLINE))
            self.setFormat(offset, 1, existing)
```

Update the test from Task 7 if needed to construct the highlighter with the new signature: `FieldHighlighter(editor.document(), registry)` still works because `editor` is optional. Update the Task 9 test invocation to pass `editor`:

```python
    highlighter = FieldHighlighter(editor.document(), registry, editor)
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: PASS — 30 tests.

- [ ] **Step 5: Commit**

```bash
git add src/ui/field_navigator.py tests/unit/test_field_navigator.py
git commit -m "feat(fields): yellow underline on the active anchor"
```

---

## Task 10: `FieldNavigator` — event filter for Ctrl+Tab

**Files:**
- Modify: `src/ui/field_navigator.py`
- Test: `tests/unit/test_field_navigator.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_field_navigator.py`:

```python
from PyQt6.QtTest import QTest
from src.ui.field_navigator import FieldNavigator


def test_ctrl_tab_selects_first_field(qtbot):
    """Ctrl+Tab from cursor at position 0 selects the first field's full range (brackets included)."""
    editor = QTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("text [first] mid [second]")  # 5-12 and 17-25

    registry = FieldRegistry(editor)
    nav = FieldNavigator(editor, registry)

    cursor = editor.textCursor()
    cursor.setPosition(0)
    editor.setTextCursor(cursor)

    QTest.keyClick(editor, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)

    sel = editor.textCursor()
    assert sel.hasSelection()
    assert (sel.selectionStart(), sel.selectionEnd()) == (5, 12)


def test_plain_tab_does_not_navigate(qtbot):
    """Plain Tab inserts a tab character — does NOT trigger field navigation."""
    editor = QTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("[a] [b]")
    cursor = editor.textCursor()
    cursor.setPosition(3)
    editor.setTextCursor(cursor)

    registry = FieldRegistry(editor)
    nav = FieldNavigator(editor, registry)

    QTest.keyClick(editor, Qt.Key.Key_Tab)  # no modifier

    sel = editor.textCursor()
    # Plain Tab inserted a `\t` — no selection
    assert not sel.hasSelection()
    assert "\t" in editor.toPlainText()


def test_ctrl_shift_tab_walks_backwards(qtbot):
    editor = QTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("[a] mid [b]")  # 0-3 and 8-11
    cursor = editor.textCursor()
    cursor.setPosition(11)  # past last
    editor.setTextCursor(cursor)

    registry = FieldRegistry(editor)
    nav = FieldNavigator(editor, registry)

    QTest.keyClick(editor, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)

    sel = editor.textCursor()
    assert (sel.selectionStart(), sel.selectionEnd()) == (8, 11)


def test_ctrl_tab_no_fields_is_silent_noop(qtbot):
    editor = QTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("no fields here")

    registry = FieldRegistry(editor)
    nav = FieldNavigator(editor, registry)

    cursor = editor.textCursor()
    cursor.setPosition(3)
    editor.setTextCursor(cursor)
    pre_pos = editor.textCursor().position()

    QTest.keyClick(editor, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)

    # No selection, no movement
    sel = editor.textCursor()
    assert not sel.hasSelection()
    assert sel.position() == pre_pos
```

Note: Qt emits `Key_Backtab` for Shift+Tab presses; we explicitly test that path.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: FAIL — `cannot import name 'FieldNavigator'`.

- [ ] **Step 3: Implement `FieldNavigator` with the event filter**

Append to `src/ui/field_navigator.py`:

```python
from PyQt6.QtCore import QObject, QEvent
from PyQt6.QtGui import QKeyEvent, QTextCursor


class FieldNavigator(QObject):
    """Captures Ctrl+Tab / Ctrl+Shift+Tab on the editor and selects the
    next/previous field. Plain Tab falls through to QTextEdit's default
    (which inserts a `\\t`)."""

    def __init__(self, editor: QTextEdit, registry: FieldRegistry):
        super().__init__(editor)
        self._editor = editor
        self._registry = registry
        editor.installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self._editor and event.type() == QEvent.Type.KeyPress:
            ke: QKeyEvent = event  # type: ignore[assignment]
            mods = ke.modifiers()
            ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
            shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
            key = ke.key()
            # Qt sends Key_Backtab when Shift is held with Tab; also accept
            # Key_Tab + Shift for completeness.
            is_tab_forward = ctrl and not shift and key == Qt.Key.Key_Tab
            is_tab_backward = ctrl and (
                key == Qt.Key.Key_Backtab
                or (shift and key == Qt.Key.Key_Tab)
            )
            if is_tab_forward:
                self.jump_next()
                return True
            if is_tab_backward:
                self.jump_prev()
                return True
        return super().eventFilter(obj, event)

    def jump_next(self) -> None:
        self._registry.cleanup_zombies()
        pos = self._editor.textCursor().position()
        anchor = self._registry.find_next(pos)
        if anchor is None:
            return
        self._select_anchor(anchor)

    def jump_prev(self) -> None:
        self._registry.cleanup_zombies()
        pos = self._editor.textCursor().position()
        anchor = self._registry.find_prev(pos)
        if anchor is None:
            return
        self._select_anchor(anchor)

    def _select_anchor(self, anchor: FieldAnchor) -> None:
        cursor = QTextCursor(self._editor.document())
        cursor.setPosition(anchor.start)
        cursor.setPosition(anchor.end, QTextCursor.MoveMode.KeepAnchor)
        self._editor.setTextCursor(cursor)
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: PASS — 34 tests.

- [ ] **Step 5: Commit**

```bash
git add src/ui/field_navigator.py tests/unit/test_field_navigator.py
git commit -m "feat(fields): Ctrl+Tab / Ctrl+Shift+Tab navigation"
```

---

## Task 11: `FieldNavigator` — mid-recording guard

**Files:**
- Modify: `src/ui/field_navigator.py`
- Test: `tests/unit/test_field_navigator.py`

The navigator needs a way to know whether recording is in progress; we pass a callable so the navigator doesn't have to depend on `MainWindow` directly.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_field_navigator.py`:

```python
def test_ctrl_tab_dropped_during_recording(qtbot):
    """When recording is active, Ctrl+Tab is dropped — selection unchanged."""
    editor = QTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("[a] [b]")

    registry = FieldRegistry(editor)
    is_recording = {"value": True}
    nav = FieldNavigator(editor, registry, is_recording_fn=lambda: is_recording["value"])

    cursor = editor.textCursor()
    cursor.setPosition(0)
    editor.setTextCursor(cursor)

    QTest.keyClick(editor, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)

    sel = editor.textCursor()
    assert not sel.hasSelection(), "Ctrl+Tab during recording must not change selection"

    # Once recording stops, Ctrl+Tab works again
    is_recording["value"] = False
    QTest.keyClick(editor, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)
    sel = editor.textCursor()
    assert sel.hasSelection()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: FAIL — `unexpected keyword argument 'is_recording_fn'`.

- [ ] **Step 3: Add the guard**

In `src/ui/field_navigator.py`, modify `FieldNavigator.__init__` and `eventFilter`:

```python
from typing import Callable, Optional


class FieldNavigator(QObject):
    def __init__(
        self,
        editor: QTextEdit,
        registry: FieldRegistry,
        is_recording_fn: Optional[Callable[[], bool]] = None,
    ):
        super().__init__(editor)
        self._editor = editor
        self._registry = registry
        self._is_recording = is_recording_fn or (lambda: False)
        editor.installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self._editor and event.type() == QEvent.Type.KeyPress:
            ke: QKeyEvent = event  # type: ignore[assignment]
            mods = ke.modifiers()
            ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
            shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
            key = ke.key()
            is_tab_forward = ctrl and not shift and key == Qt.Key.Key_Tab
            is_tab_backward = ctrl and (
                key == Qt.Key.Key_Backtab
                or (shift and key == Qt.Key.Key_Tab)
            )
            if is_tab_forward or is_tab_backward:
                if self._is_recording():
                    # Drop the navigation event during recording. Returning True
                    # also prevents the editor's default handling of Ctrl+Tab.
                    return True
                if is_tab_forward:
                    self.jump_next()
                else:
                    self.jump_prev()
                return True
        return super().eventFilter(obj, event)
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: PASS — 35 tests.

- [ ] **Step 5: Commit**

```bash
git add src/ui/field_navigator.py tests/unit/test_field_navigator.py
git commit -m "feat(fields): mid-recording guard on Ctrl+Tab"
```

---

## Task 12: Re-dictate-fills-flow integration test

**Files:**
- Test: `tests/unit/test_field_navigator.py`

This is an end-to-end test inside the editor — no STT, no streaming. It exercises the full select-then-replace flow to confirm anchor state transitions correctly when text is inserted via the same primitive the dictation pipeline uses.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_field_navigator.py`:

```python
def test_select_replace_flips_anchor_state_to_filled(qtbot):
    """Simulate the dictation-replace flow: Ctrl+Tab to select a field, then
    replace via cursor.removeSelectedText() + insertText(), as
    TextStreamingController would do via begin() + insertText.
    """
    editor = QTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("The pancreas is [normal].")  # field at [16, 24]

    registry = FieldRegistry(editor)
    nav = FieldNavigator(editor, registry)

    # Land on the field
    QTest.keyClick(editor, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)
    sel = editor.textCursor()
    assert (sel.selectionStart(), sel.selectionEnd()) == (16, 24)

    # Replace the selection with dictated text — same primitive the streaming pipeline uses
    sel.removeSelectedText()
    sel.insertText("atrophic")

    # Anchor state should be filled, end position updated
    anchors = registry.anchors()
    assert len(anchors) == 1
    assert anchors[0].state == "filled"
    assert (anchors[0].start, anchors[0].end) == (16, 24)
    # Editor text shows the replacement
    assert editor.toPlainText() == "The pancreas is atrophic."


def test_re_dictate_into_filled_field_replaces_again(qtbot):
    """After a fill, Ctrl+Shift+Tab can return to the field and another replace works."""
    editor = QTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("[normal] tail")  # field at [0, 8]

    registry = FieldRegistry(editor)
    nav = FieldNavigator(editor, registry)

    # First fill
    QTest.keyClick(editor, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)
    cursor = editor.textCursor()
    cursor.removeSelectedText()
    cursor.insertText("atrophic")

    # Move cursor past the field
    cursor.setPosition(11)
    editor.setTextCursor(cursor)

    # Walk back
    QTest.keyClick(editor, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    sel = editor.textCursor()
    assert sel.hasSelection()
    assert sel.selectedText() == "atrophic"

    # Replace again
    sel.removeSelectedText()
    sel.insertText("enlarged")

    anchors = registry.anchors()
    assert len(anchors) == 1
    assert anchors[0].state == "filled"
    assert editor.toPlainText() == "enlarged tail"
```

- [ ] **Step 2: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_field_navigator.py -v`
Expected: PASS — 37 tests. (No code changes; this exercises existing behavior.)

If a test fails, the position-update rules from Task 3 or the registry from Task 5 has a bug — fix there, not here.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_field_navigator.py
git commit -m "test(fields): end-to-end select-replace integration tests"
```

---

## Task 13: Wire into `main.py`

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: Add `_wire_field_navigator` helper**

In `src/main.py`, immediately before the `def main():` line, add a new helper:

```python
from src.ui.field_navigator import FieldRegistry, FieldHighlighter, FieldNavigator


def _wire_field_navigator(window, recording_state) -> tuple:
    """Attach field detection, highlighting, and Ctrl+Tab navigation to the editor.

    Returns the registry/highlighter/navigator triple so main() can keep
    references alive (otherwise the highlighter — a QObject child of the
    document — is fine, but the navigator is a child of the editor and
    auto-managed; the registry has no parent and would be GC'd if dropped).
    """
    registry = FieldRegistry(window.editor)
    highlighter = FieldHighlighter(window.editor.document(), registry, window.editor)
    navigator = FieldNavigator(
        window.editor,
        registry,
        is_recording_fn=lambda: recording_state["active"],
    )
    return registry, highlighter, navigator
```

- [ ] **Step 2: Call the helper from `main()`**

In `src/main.py`'s `main()` function, immediately after the existing line:

```python
    window.on_toggle_recording = handle_trigger
```

(in the dictation-trigger setup block — search for `window.on_toggle_recording = handle_trigger`)

…add:

```python
    # Field navigation: detect [bracket] fields, highlight as pills,
    # and intercept Ctrl+Tab in the editor to walk between them.
    _field_registry, _field_highlighter, _field_navigator = _wire_field_navigator(
        window, recording_state
    )
```

The leading underscores keep the names lint-quiet — we hold them only to prevent garbage collection.

- [ ] **Step 3: Verify imports clean and tests still pass**

Run: `.venv/Scripts/python.exe -c "import src.main; print('OK')"`
Expected: `OK`

Run: `.venv/Scripts/python.exe -m pytest tests/ -q --ignore=tests/unit/test_profiling_harness.py --ignore=tests/unit/test_profiling_scenarios.py --ignore=tests/unit/test_profile_pipeline_dryrun.py`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/main.py
git commit -m "feat(main): wire field navigator into MainWindow editor"
```

---

## Task 14: Manual smoke test

**Files:** none (verification only)

This is a hands-on confirmation that the feature works in the actual app. Do not check off the slice as done until every step here passes.

- [ ] **Step 1: Launch the app**

Run: `.venv/Scripts/python.exe -m src.main`

- [ ] **Step 2: Paste a template**

Click into the editor and paste:

```
The pancreas is [normal] without [acute] findings. The kidneys are [size].
```

Expected: three lavender pills visible. Brackets read invisibly inside each pill. Default text ("normal", "acute", "size") visible inside each.

- [ ] **Step 3: Ctrl+Tab to first field**

Press Ctrl+Tab.
Expected: the first pill (`[normal]`) is now selected (range highlight + yellow underline on the active anchor).

- [ ] **Step 4: Dictate a replacement**

Press F4 (or click Record), say "atrophic", press F4 to stop.
Expected: the first field becomes teal "atrophic" without brackets, no pill. Cursor at end of "atrophic".

- [ ] **Step 5: Walk forward**

Press Ctrl+Tab.
Expected: jumps to `[acute]` pill (selected with yellow underline).

Press Ctrl+Tab again.
Expected: jumps to `[size]` pill.

- [ ] **Step 6: Walk back to filled field**

Press Ctrl+Shift+Tab twice.
Expected: walks back to `[acute]`, then back to "atrophic" (the filled field). Confirm "atrophic" is selected as a navigable anchor.

- [ ] **Step 7: Plain Tab still inserts a tab**

Click into the editor at any non-field position, press Tab (no Ctrl).
Expected: a `\t` character is inserted; no selection change, no field navigation.

- [ ] **Step 8: Mid-recording Ctrl+Tab is dropped**

Press F4 to start recording, then press Ctrl+Tab during the recording.
Expected: nothing visible happens — selection unchanged. Stop recording with F4.

- [ ] **Step 9: Manual deletion drops anchor**

Place cursor before `[size]`, select all text up to and including `]`, delete.
Press Ctrl+Tab.
Expected: cycles only through "atrophic" and `[acute]` — no zombie anchor.

- [ ] **Step 10: Commit a smoke-test note**

Only after every step above passes, leave a note in the commit log:

```bash
git commit --allow-empty -m "test(fields): manual smoke test passed"
```

If any step fails, file the bug in the existing test suite (preferred) and fix at the right task before re-running this smoke test from the top.

---

## Task 15: Profiling pass

**Files:**
- Create: `tools/profiling/scenarios.py` (or modify if existing)
- Create: `benchmarks/field_navigation_template.txt`

Per the user's standing default-plan-template: every plan ends with a profiling pass.

- [ ] **Step 1: Create a long template fixture**

Create `benchmarks/field_navigation_template.txt` containing 200 lines of report-like text with 30 `[default]` fields scattered throughout. (Hand-write or programmatically generate; commit the file.) Add it to `.gitignore` if benchmarks are gitignored — verify in `.gitignore` first; if so, document in this task that the fixture is generated at first run instead.

Example generator if generating instead of committing the fixture:

```python
# tools/profiling/_field_template.py
def generate_template() -> str:
    organs = ["pancreas", "liver", "spleen", "kidneys", "adrenals", "bowel"]
    findings = ["normal", "atrophic", "enlarged", "without focal lesion", "unremarkable"]
    lines = []
    for i in range(200):
        organ = organs[i % len(organs)]
        finding = findings[i % len(findings)]
        if i % 7 == 0:
            lines.append(f"The {organ} is [{finding}] in appearance.")
        else:
            lines.append(f"The {organ} demonstrates {finding} morphology.")
    return "\n".join(lines)
```

- [ ] **Step 2: Add a profiling scenario**

In `tools/profiling/scenarios.py`, append a scenario that:

```python
def field_highlight_scenario(profiler) -> dict:
    """Measure highlighter wall-time on a 200-line template with 30 fields."""
    import time
    from PyQt6.QtWidgets import QApplication, QTextEdit
    from src.ui.field_navigator import FieldRegistry, FieldHighlighter
    from tools.profiling._field_template import generate_template

    app = QApplication.instance() or QApplication([])
    editor = QTextEdit()
    text = generate_template()

    profiler.start("field_text_set")
    editor.setPlainText(text)
    profiler.stop("field_text_set")

    profiler.start("field_registry_seed")
    registry = FieldRegistry(editor)
    profiler.stop("field_registry_seed")

    profiler.start("field_highlighter_first_pass")
    highlighter = FieldHighlighter(editor.document(), registry, editor)
    highlighter.rehighlight()
    profiler.stop("field_highlighter_first_pass")

    return {"anchors": len(registry.anchors())}
```

- [ ] **Step 3: Run the profiler**

Run: `.venv/Scripts/python.exe -m tools.profile_pipeline`
Expected: report includes per-step wall-time. Acceptable: highlighter < 5 ms per textChanged on the test machine.

If above threshold, the likely fix is a per-block dirty bit so the highlighter skips unchanged blocks. Add that fix here, re-run, then commit.

- [ ] **Step 4: Commit**

```bash
git add tools/profiling/ benchmarks/
git commit -m "perf(fields): add highlighter profiling scenario; verify <5ms per pass"
```

---

## Task 16: Dead-code + readability sweep

**Files:** all changed files in this slice

Per the user's standing default-plan-template: every plan ends with a readability sweep.

- [ ] **Step 1: Re-read `field_navigator.py` end-to-end**

Confirm:
- Each class < 120 lines
- Each method < 30 lines (the position-update function may be ~30 lines; that's fine — splitting cases obscures the intent)
- No `print()` debug calls
- No leftover `# TODO` / `# FIXME`
- Comments only where the WHY is non-obvious (per user preference: sparse why-only)

- [ ] **Step 2: Re-read the new helper in `main.py`**

`_wire_field_navigator` should look like the other `_wire_*` helpers — compact, single concern, signature minimal.

- [ ] **Step 3: Grep for dead branches**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q --ignore=tests/unit/test_profiling_harness.py --ignore=tests/unit/test_profiling_scenarios.py --ignore=tests/unit/test_profile_pipeline_dryrun.py --cov=src.ui.field_navigator --cov-report=term-missing`

If `pytest-cov` isn't installed, skip the coverage report and just visually inspect the file for branches no test exercises. Any uncovered branch is a candidate for either deletion or a missing test.

- [ ] **Step 4: Commit any cleanup**

```bash
git add src/ui/field_navigator.py src/main.py
git commit -m "refactor(fields): readability sweep"
```

If no changes needed, commit empty:

```bash
git commit --allow-empty -m "chore(fields): readability sweep complete (no changes)"
```

---

## Done criteria

- [ ] All 37+ tests in `tests/unit/test_field_navigator.py` pass
- [ ] `import src.main` is clean
- [ ] Full pytest suite (excluding pyinstrument-dependent tests) passes
- [ ] Manual smoke test (Task 14) passes every step
- [ ] Profiling shows highlighter < 5 ms per pass on the long-template fixture
- [ ] No `TODO` / `FIXME` markers in new code
