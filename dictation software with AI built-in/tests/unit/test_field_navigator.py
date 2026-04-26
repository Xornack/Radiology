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
