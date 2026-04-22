"""System-wide hotkey registration via Win32 RegisterHotKey.

Unlike Qt's ApplicationShortcut (which only fires when the registering window
has focus), a hotkey registered here fires regardless of which window owns
the keyboard focus. This is what lets a user focus Chrome/Outlook/Notepad,
press F4, and have dictation trigger in our app.
"""
import ctypes
from ctypes import wintypes
from loguru import logger
from PyQt6.QtCore import (
    QObject,
    pyqtSignal,
    QAbstractNativeEventFilter,
    QCoreApplication,
)


# Win32 constants — see WinUser.h
WM_HOTKEY = 0x0312
MOD_NONE = 0x0000
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000   # Win7+: don't fire on OS auto-repeat

# Virtual-key codes (subset — extend as needed)
VK_F4 = 0x73


class _HotkeyEventFilter(QAbstractNativeEventFilter):
    """Route WM_HOTKEY messages matching a given id to an emit function."""
    def __init__(self, hotkey_id: int, emit_fn):
        super().__init__()
        self._hotkey_id = hotkey_id
        self._emit = emit_fn

    def nativeEventFilter(self, event_type, message):
        # Windows delivers native events as MSG structs; skip otherwise.
        if event_type != b"windows_generic_MSG":
            return False, 0
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id:
            self._emit()
            return True, 0
        return False, 0


class GlobalHotkey(QObject):
    """
    Register a system-wide Windows hotkey. Emits `activated` (no args) whenever
    the key combination is pressed, anywhere on the desktop.

    Signal emission happens on the GUI thread because WM_HOTKEY is delivered
    to the thread's message queue — in a Qt app, that's the main thread.
    """
    activated = pyqtSignal()

    def __init__(
        self,
        vk: int = VK_F4,
        modifiers: int = MOD_NOREPEAT,
        hotkey_id: int = 1,
        parent=None,
    ):
        super().__init__(parent)
        self._vk = vk
        self._modifiers = modifiers
        self._id = hotkey_id
        self._registered = False
        self._filter = None

    def register(self) -> bool:
        """Attempt to register the hotkey. Returns True on success.

        Failure is usually because another app already holds the combination.
        The caller should fall back to an app-local shortcut in that case.
        """
        user32 = ctypes.windll.user32
        if not user32.RegisterHotKey(None, self._id, self._modifiers, self._vk):
            err = ctypes.get_last_error()
            logger.warning(
                f"RegisterHotKey failed for vk=0x{self._vk:02x} "
                f"modifiers=0x{self._modifiers:04x} (err={err}); "
                "global hotkey unavailable — app-local shortcut still works "
                "when the dictation window has focus."
            )
            return False
        self._registered = True
        self._filter = _HotkeyEventFilter(self._id, self.activated.emit)
        app = QCoreApplication.instance()
        if app is not None:
            app.installNativeEventFilter(self._filter)
        logger.info(
            f"Global hotkey registered: vk=0x{self._vk:02x} "
            f"modifiers=0x{self._modifiers:04x}"
        )
        return True

    def unregister(self):
        """Remove the hotkey and native event filter. Safe to call repeatedly."""
        if not self._registered:
            return
        ctypes.windll.user32.UnregisterHotKey(None, self._id)
        app = QCoreApplication.instance()
        if self._filter is not None and app is not None:
            app.removeNativeEventFilter(self._filter)
        self._registered = False
        self._filter = None
