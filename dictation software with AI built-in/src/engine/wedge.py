"""Keyboard wedge — types text into the currently focused Windows window.

Uses PostMessageW(WM_CHAR, ...) against the focused child control of the
foreground app, one UTF-16 code unit at a time. This bypasses:

  - The global raw-input queue (where Win11 text surfaces were silently
    truncating batched KEYEVENTF_UNICODE frames mid-stream).
  - Low-level keyboard hooks (WH_KEYBOARD_LL) installed by AV/EDR, medical
    dictation drivers, remappers, etc. — these can translate synthetic
    KEYEVENTF_UNICODE events into virtual-key events and lose the keyup,
    producing stuck-key runs like ".........." at the end of a dictation.

WM_CHAR + PostMessage is the canonical accessibility-tool pattern for
typing into classic edit controls (Notepad, Word, Outlook) and most web
text fields (Chrome, Edge, Electron) that accept keyboard-style text
entry. Apps that only consume raw input (games, some kiosks) won't
receive it — those aren't targets for this wedge.
"""
import ctypes
from ctypes import wintypes
from loguru import logger

WM_CHAR = 0x0102

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.GetWindowThreadProcessId.argtypes = [
    wintypes.HWND, ctypes.POINTER(wintypes.DWORD)
]
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD
_user32.AttachThreadInput.argtypes = [
    wintypes.DWORD, wintypes.DWORD, wintypes.BOOL
]
_user32.AttachThreadInput.restype = wintypes.BOOL
_user32.GetFocus.restype = wintypes.HWND
_user32.PostMessageW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
]
_user32.PostMessageW.restype = wintypes.BOOL


def _to_utf16_code_units(text: str) -> list[int]:
    """Flatten a Python str into UTF-16 code units (surrogate pairs for SMP)."""
    units: list[int] = []
    for char in text:
        cp = ord(char)
        if cp <= 0xFFFF:
            units.append(cp)
        else:
            cp -= 0x10000
            units.append(0xD800 + (cp >> 10))
            units.append(0xDC00 + (cp & 0x3FF))
    return units


def _focused_hwnd() -> int:
    """Return the HWND of the focused control within the foreground app, or 0.

    GetFocus only reports focus within the calling thread's input queue, so
    we temporarily attach to the target's thread input to read its focus.
    AttachThreadInput can disrupt focus if left attached, so the detach is
    in a finally block.
    """
    hwnd_fg = _user32.GetForegroundWindow()
    if not hwnd_fg:
        return 0
    our_tid = _kernel32.GetCurrentThreadId()
    target_tid = _user32.GetWindowThreadProcessId(hwnd_fg, None)
    if not target_tid or target_tid == our_tid:
        return hwnd_fg
    if not _user32.AttachThreadInput(our_tid, target_tid, True):
        # If we can't attach (different desktop, elevated target, etc.),
        # fall back to the top-level foreground window. Classic apps will
        # route WM_CHAR to their focused child via default window procs.
        return hwnd_fg
    try:
        focused = _user32.GetFocus()
    finally:
        _user32.AttachThreadInput(our_tid, target_tid, False)
    return focused or hwnd_fg


def type_text(text: str):
    """Simulate text entry into the currently focused Windows window.

    Delivers each UTF-16 code unit as a WM_CHAR message posted directly to
    the target's message queue. Ordering is preserved because a window's
    message queue is strictly FIFO within a single posting thread.
    """
    if not text:
        return

    target = _focused_hwnd()
    if not target:
        logger.error(f"Wedge: no focused window; cannot post {text!r}")
        return

    for unit in _to_utf16_code_units(text):
        if not _user32.PostMessageW(target, WM_CHAR, unit, 0):
            err = _kernel32.GetLastError()
            logger.error(
                f"PostMessageW(hwnd={target:#x}, WM_CHAR, U+{unit:04X}) "
                f"failed (GetLastError={err}); remainder of {text!r} not posted"
            )
            return
