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
