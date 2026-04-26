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
