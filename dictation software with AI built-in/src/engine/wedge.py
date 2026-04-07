import ctypes
from ctypes import wintypes

# Win32 Constants
INPUT_KEYBOARD = 1
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_KEYUP = 0x0002

# Standard US Keyboard Scan Codes (incomplete list, but sufficient for MVP)
SCAN_CODES = {
    '1': 0x02, '2': 0x03, '3': 0x04, '4': 0x05, '5': 0x06, '6': 0x07, '7': 0x08, '8': 0x09, '9': 0x0A, '0': 0x0B,
    'q': 0x10, 'w': 0x11, 'e': 0x12, 'r': 0x13, 't': 0x14, 'y': 0x15, 'u': 0x16, 'i': 0x17, 'o': 0x18, 'p': 0x19,
    'a': 0x1E, 's': 0x1F, 'd': 0x20, 'f': 0x21, 'g': 0x22, 'h': 0x23, 'j': 0x24, 'k': 0x25, 'l': 0x26,
    'z': 0x2C, 'x': 0x2D, 'c': 0x2E, 'v': 0x2F, 'b': 0x30, 'n': 0x31, 'm': 0x32,
    ' ': 0x39, '.': 0x34, ',': 0x33, '\n': 0x1C, '-': 0x0C
}

# Win32 Structures
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class INPUT_I(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT),
                ("mi", ctypes.c_byte * 24), # Padding for union
                ("hi", ctypes.c_byte * 24)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD),
                ("ii", INPUT_I)]

def _send_key(scan_code: int, key_up: bool = False):
    """
    Core Win32 SendInput call using scan codes for maximum compatibility.
    """
    flags = KEYEVENTF_SCANCODE
    if key_up:
        flags |= KEYEVENTF_KEYUP
        
    extra = ctypes.c_ulong(0)
    ii_ = INPUT_I()
    ii_.ki = KEYBDINPUT(0, scan_code, flags, 0, ctypes.pointer(extra))
    
    input_obj = INPUT(INPUT_KEYBOARD, ii_)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(input_obj), ctypes.sizeof(input_obj))

def type_text(text: str):
    """
    Simulates keyboard input into the currently focused window.
    """
    for char in text.lower():
        if char in SCAN_CODES:
            code = SCAN_CODES[char]
            _send_key(code, key_up=False) # Press
            _send_key(code, key_up=True)  # Release
        else:
            # For characters not in our scan code map, 
            # we skip them to avoid unintended behavior in clinical apps.
            pass
