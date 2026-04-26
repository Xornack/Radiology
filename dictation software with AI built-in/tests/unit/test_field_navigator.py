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
