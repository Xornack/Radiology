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

# ULONG_PTR: pointer-sized unsigned int (8B on 64-bit, 4B on 32-bit).
# wintypes has no ULONG_PTR, and ctypes.c_ulong is 4B on Win64 (LLP64) — so
# using c_ulong for dwExtraInfo would under-size KEYBDINPUT/MOUSEINPUT.
ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


# MOUSEINPUT/HARDWAREINPUT must be the real types (not c_byte placeholders):
# SendInput validates cbSize == sizeof(INPUT) and rejects mismatches with
# ERROR_INVALID_PARAMETER. On 64-bit, the real MOUSEINPUT is 32B — a 24B
# placeholder makes sizeof(INPUT) = 32 instead of 40, and every call fails.
class INPUT_I(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT),
                ("mi", MOUSEINPUT),
                ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD),
                ("ii", INPUT_I)]


_user32 = ctypes.windll.user32
_user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
_user32.SendInput.restype = wintypes.UINT


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

    for i, unit in enumerate(code_units):
        for j, key_up in enumerate((False, True)):
            flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if key_up else 0)
            idx = 2 * i + j
            arr[idx].type = INPUT_KEYBOARD
            arr[idx].ii.ki = KEYBDINPUT(0, unit, flags, 0, 0)

    sent = _user32.SendInput(n_events, ctypes.byref(arr), ctypes.sizeof(INPUT))
    if sent != n_events:
        err = ctypes.windll.kernel32.GetLastError()
        logger.error(
            f"SendInput delivered {sent}/{n_events} events for {text!r} "
            f"(GetLastError={err})"
        )
