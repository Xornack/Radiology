"""Field detection, highlighting, and Ctrl+Tab navigation for the
dictation editor.

A "field" is a `[default text]` placeholder in the editor. The user
navigates between fields with Ctrl+Tab / Ctrl+Shift+Tab; dictation
replaces the active field. Filled fields persist as navigable anchors
so the user can jump back and re-dictate.

See docs/superpowers/specs/2026-04-26-field-navigation-design.md for
the full design and decision log.
"""
import re
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
