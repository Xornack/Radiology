"""Keyboard wedge — types text into the currently focused Windows window.

Implementation uses KEYEVENTF_UNICODE for every character and batches the
entire string into a single SendInput call. This is the approach used by
mature input-simulation tools (AutoHotkey's SendText, nircmd) because:

  - Unicode input maps directly to WM_CHAR messages, bypassing the keyboard
    layout translation that scan-code input goes through. Modern Windows 11
    apps (Notepad WinUI, Chrome, Outlook, Electron surfaces) need WM_CHAR;
    scancode-only input was unreliable against them.
  - Batching N events into one SendInput call delivers them atomically as a
    single input frame, which modern apps consume reliably. One-call-per-key
    at 50k+ chars/sec caused dropped characters in the old path.
  - No shift emulation needed — the Unicode codepoint encodes case directly.
"""
import ctypes
from ctypes import wintypes
from loguru import logger

# Win32 constants
INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class INPUT_I(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT),
                ("mi", ctypes.c_byte * 24),
                ("hi", ctypes.c_byte * 24)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD),
                ("ii", INPUT_I)]


def _to_utf16_code_units(text: str) -> list[int]:
    """Flatten a Python str into UTF-16 code units (surrogate pairs for SMP)."""
    units: list[int] = []
    for char in text:
        cp = ord(char)
        if cp <= 0xFFFF:
            units.append(cp)
        else:
            # Supplementary-plane char: encode as surrogate pair
            cp -= 0x10000
            units.append(0xD800 + (cp >> 10))
            units.append(0xDC00 + (cp & 0x3FF))
    return units


def type_text(text: str):
    """Simulate keyboard input by typing `text` into the focused Windows window.

    Batches all key-down/key-up events into a single SendInput call using
    KEYEVENTF_UNICODE so delivery is atomic and compatible with modern apps.
    """
    if not text:
        return

    code_units = _to_utf16_code_units(text)
    n_events = 2 * len(code_units)   # down + up per unit

    InputArray = INPUT * n_events
    arr = InputArray()
    # Keep the c_ulong extras alive for the duration of the SendInput call
    # (KEYBDINPUT holds a pointer into these objects).
    extras = [ctypes.c_ulong(0) for _ in range(n_events)]

    for i, unit in enumerate(code_units):
        for j, key_up in enumerate((False, True)):
            flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if key_up else 0)
            idx = 2 * i + j
            arr[idx].type = INPUT_KEYBOARD
            arr[idx].ii.ki = KEYBDINPUT(
                0, unit, flags, 0, ctypes.pointer(extras[idx])
            )

    sent = ctypes.windll.user32.SendInput(
        n_events, ctypes.byref(arr), ctypes.sizeof(INPUT)
    )
    if sent != n_events:
        err = ctypes.windll.kernel32.GetLastError()
        logger.warning(
            f"SendInput delivered {sent}/{n_events} events for {text!r} "
            f"(GetLastError={err})"
        )
