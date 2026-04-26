# tests/unit/test_field_navigator.py
from src.ui.field_navigator import FieldAnchor, find_brackets


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

    found = registry.find_prev(0)
    assert found is not None and found.default == "b"


from PyQt6.QtGui import QColor, QTextCursor
from src.ui.field_navigator import FieldHighlighter, PILL_BG, PILL_TEXT


def test_highlighter_paints_pill_on_unfilled(qtbot):
    """Bracketed text gets pill background and dark text on the inner chars; brackets get color-matched-to-bg foreground."""
    editor = QTextEdit()
    qtbot.addWidget(editor)
    editor.setPlainText("[a]")

    registry = FieldRegistry(editor)
    highlighter = FieldHighlighter(editor.document(), registry)
    highlighter.rehighlight()

    # QSyntaxHighlighter applies layout-level format overlays (not document
    # character formats). Read them via QTextLayout.formats().
    block = editor.document().firstBlock()
    layout_formats = block.layout().formats()

    # Build position → format map. Each FormatRange covers [start, start+length).
    fmt_at = {}
    for fr in layout_formats:
        for offset in range(fr.start, fr.start + fr.length):
            fmt_at[offset] = fr.format

    # Opening bracket at position 0: invisible (fg matches bg)
    assert fmt_at[0].foreground().color() == QColor(PILL_BG)
    assert fmt_at[0].background().color() == QColor(PILL_BG)

    # Inner char at position 1: dark text on lavender
    assert fmt_at[1].foreground().color() == QColor(PILL_TEXT)
    assert fmt_at[1].background().color() == QColor(PILL_BG)

    # Closing bracket at position 2: invisible
    assert fmt_at[2].foreground().color() == QColor(PILL_BG)
    assert fmt_at[2].background().color() == QColor(PILL_BG)
