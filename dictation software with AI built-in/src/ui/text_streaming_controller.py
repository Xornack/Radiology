"""Partial-text state machine for the dictation editor.

Extracted from MainWindow because this is the trickiest code in the UI:
it owns the live region between committed and partial text, rewrites in
place on each streaming tick, and reconciles the orchestrator's Stop-path
output with any committed chunks that already landed.

MainWindow keeps thin wrappers (`begin_streaming`, `update_partial`, etc.)
that delegate here, so public callers don't have to know about the split.
"""
from PyQt6.QtGui import QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import QTextEdit


# Characters that belong to the word on their LEFT — if a commit chunk
# begins with one of these (e.g. a lone "?" from "question mark"), the
# controller must not wedge a space in front of it.
_ATTACHING_PUNCTUATION = set('.,?!;:)]}”"')


class TextStreamingController:
    """Manages the live-partial region inside a QTextEdit during dictation.

    State:
      - `_committed_end`: inclusive anchor — everything below this position
        is locked-in committed text that partials must not overwrite.
      - `_partial_end`: end of the live partial region. `[committed_end,
        partial_end]` is what update_partial() replaces in place each tick.
      - `_capitalize_first`: True if the first character of the next text
        should be uppercased (start of dictation, or immediately after a
        sentence terminator in the surrounding editor text).

    Both positions are -1 when no streaming session is active.
    """

    def __init__(
        self,
        editor: QTextEdit,
        dictation_format: QTextCharFormat,
        profiler_getter=None,
    ):
        """profiler_getter: callable returning the current profiler (or None).
        Using a getter lets MainWindow assign `self.profiler = p` after
        construction and have those calls flow through to us without any
        additional wiring."""
        self._editor = editor
        self._format = dictation_format
        self._profiler_getter = profiler_getter
        self._committed_end: int = -1
        self._partial_end: int = -1
        self._capitalize_first: bool = True

    # Introspection helpers — used by tests and by MainWindow's status wiring.
    @property
    def is_streaming(self) -> bool:
        return self._committed_end >= 0

    @property
    def committed_end(self) -> int:
        return self._committed_end

    @property
    def partial_end(self) -> int:
        return self._partial_end

    @property
    def capitalize_first(self) -> bool:
        return self._capitalize_first

    def begin(self) -> None:
        """Anchor a streaming session at the current cursor position.

        If there is an active selection, the selected text is removed first so
        dictation replaces it (standard "type over selection" behavior).
        """
        cursor = self._editor.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()
            self._editor.setTextCursor(cursor)
        pos = cursor.position()
        self._committed_end = pos
        self._partial_end = pos
        doc_text = self._editor.toPlainText()
        stripped_prefix = doc_text[:pos].rstrip()
        self._capitalize_first = (
            not stripped_prefix
            or stripped_prefix[-1] in ".?!"
        )

    def update_partial(self, text: str) -> None:
        """Replace `[committed_end, partial_end]` with `text`."""
        if self._committed_end < 0:
            return
        profiler = self._profiler_getter() if self._profiler_getter else None
        if profiler:
            profiler.start("partial_replace")
        if text:
            text = self._apply_first_letter_case(text)
            if self._needs_leading_space_at(self._committed_end, text):
                text = " " + text
        cursor = self._editor.textCursor()
        cursor.setPosition(self._committed_end)
        cursor.setPosition(self._partial_end, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text, self._format)
        self._partial_end = self._committed_end + len(text)
        self._editor.ensureCursorVisible()
        if profiler:
            profiler.stop("partial_replace")

    def on_commit(self, text: str) -> None:
        """Lock the current partial region as committed.

        Replaces `[committed_end, partial_end]` with `text` (the commit
        transcription, which can differ from the last displayed partial since
        the STT has more audio context), then advances committed_end so
        subsequent update_partial calls don't overwrite the locked text.
        """
        if self._committed_end < 0:
            return
        if text:
            text = self._apply_first_letter_case(text)
            if self._needs_leading_space_at(self._committed_end, text):
                text = " " + text
        cursor = self._editor.textCursor()
        cursor.setPosition(self._committed_end)
        cursor.setPosition(self._partial_end, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text, self._format)
        new_end = self._committed_end + len(text)
        self._committed_end = new_end
        self._partial_end = new_end
        # After the first commit, subsequent chunks are mid-sentence — the
        # session-start capitalization has already been applied.
        self._capitalize_first = False
        self._editor.ensureCursorVisible()

    def commit_partial(self, text: str) -> None:
        """Replace the live partial region with the final text and end streaming.

        `text` is the orchestrator's Stop-path output: for in-app mode with
        prior commits, it's the REMAINDER only (committed chunks stay put in
        the editor via prior on_commit calls). For wedge/no-commits, it's the
        whole transcribe. Either way, replacing `[committed_end, partial_end]`
        does the right thing — that range is the live partial in both cases.
        """
        if self._committed_end < 0:
            if text:
                self._editor.append(text)
            return

        if text:
            text = self._apply_first_letter_case(text)
            if self._needs_leading_space_at(self._committed_end, text):
                text = " " + text

        cursor = self._editor.textCursor()
        cursor.setPosition(self._committed_end)
        cursor.setPosition(self._partial_end, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        if text:
            cursor.insertText(text, self._format)

        self._editor.setTextCursor(cursor)
        self._editor.setCurrentCharFormat(QTextCharFormat())

        self._committed_end = -1
        self._partial_end = -1
        self._capitalize_first = True
        self._editor.ensureCursorVisible()

    def _apply_first_letter_case(self, text: str) -> str:
        """Uppercase or lowercase the first letter per the session's cap-first flag.

        Normalizes text from either source (orchestrator output, which may be
        uncapitalized in-app, or streaming partials, which cap by default) so
        the first letter matches editor context.
        """
        if not text:
            return text
        if self._capitalize_first:
            return text[0].upper() + text[1:]
        return text[0].lower() + text[1:]

    def _needs_leading_space_at(self, pos: int, incoming: str = "") -> bool:
        """True if inserting `incoming` at `pos` needs a leading space.

        Dynamically checks the editor content — works for both session-start
        (pos follows prior user text) and mid-session (pos follows a previous
        committed chunk).

        When `incoming` starts with a punctuation mark that typographically
        attaches to the previous word (e.g. a lone `?` commit from the
        phrase "question mark"), we skip the space even if the prior char
        isn't whitespace — otherwise the editor ends up with "clear ?".
        """
        if pos <= 0:
            return False
        if incoming and incoming[0] in _ATTACHING_PUNCTUATION:
            return False
        doc = self._editor.toPlainText()
        if pos > len(doc):
            return False
        return doc[pos - 1] not in " \t\n"

