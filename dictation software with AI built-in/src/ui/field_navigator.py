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
import uuid
from dataclasses import dataclass
from typing import Callable, Literal, Optional

from PyQt6.QtCore import Qt, QObject, QEvent
from PyQt6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QKeyEvent, QTextCursor
from PyQt6.QtWidgets import QTextEdit


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
        editor.document().contentsChange.connect(self._on_contents_change)

    def anchors(self) -> list[FieldAnchor]:
        """Anchors in document order. Returns the live list — callers must
        not mutate it."""
        return self._anchors

    def cleanup_zombies(self) -> None:
        """Drop anchors whose range collapsed and never got refilled.

        Called before each Ctrl+Tab traversal so a deleted-with-no-replacement
        field doesn't linger as a zero-length zombie.
        """
        self._anchors = [a for a in self._anchors if a.end > a.start]

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
        """Anchor with the largest end <= `pos`.

        Wraps to the last anchor if none qualify and the list is non-empty.
        """
        if not self._anchors:
            return None
        for a in reversed(self._anchors):
            if a.end <= pos:
                return a
        return self._anchors[-1]

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

    Filled anchors get the existing dictation-teal foreground.

    The anchor containing the editor's cursor (if any) additionally gets
    a yellow underline merged with the pill or filled format.
    """

    def __init__(self, document, registry: FieldRegistry, editor: "QTextEdit | None" = None):
        super().__init__(document)
        self._registry = registry
        self._editor = editor

    def highlightBlock(self, text: str) -> None:
        block_start = self.currentBlock().position()
        block_end = block_start + len(text)
        active_pos = self._editor.textCursor().position() if self._editor else -1
        for anchor in self._registry.anchors():
            # Skip anchors that don't intersect this block
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

    def _paint_filled(self, start: int, end: int) -> None:
        """Paint filled anchor with teal foreground."""
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(FILLED_TEXT))
        self.setFormat(start, end - start, fmt)

    def _paint_active_outline(self, start: int, end: int) -> None:
        """Add yellow underline to each char in [start, end), preserving
        whatever pill/filled format is already applied."""
        for offset in range(start, end):
            existing = self.format(offset)
            existing.setFontUnderline(True)
            existing.setUnderlineColor(QColor(ACTIVE_OUTLINE))
            self.setFormat(offset, 1, existing)


class FieldNavigator(QObject):
    """Captures Ctrl+Tab / Ctrl+Shift+Tab on the editor and selects the
    next/previous field. Plain Tab falls through to QTextEdit's default
    (which inserts a `\\t`)."""

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
        if obj is not self._editor:
            return super().eventFilter(obj, event)
        et = event.type()
        # ShortcutOverride: Qt's shortcut framework binds Ctrl+Shift+Tab to
        # the standard PrevChild action (and similar). If we don't claim the
        # key here, Qt routes it to the shortcut handler instead of delivering
        # a KeyPress to us. Accepting the override tells Qt "this widget owns
        # this key" and Qt then delivers it as a normal KeyPress.
        if et not in (QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride):
            return super().eventFilter(obj, event)

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
        if not (is_tab_forward or is_tab_backward):
            return super().eventFilter(obj, event)

        if et == QEvent.Type.ShortcutOverride:
            # Claim the key — prevents Qt's shortcut framework from
            # consuming it. The actual navigation runs on the KeyPress
            # that Qt will subsequently deliver.
            event.accept()
            return True

        # KeyPress
        if self._is_recording():
            # Drop the navigation event during recording. Returning True
            # also prevents the editor's default handling of Ctrl+Tab.
            return True
        if is_tab_forward:
            self.jump_next()
        else:
            self.jump_prev()
        return True

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
