"""Unit tests for the Win32 WM_HOTKEY native event filter.

The RegisterHotKey call itself is an OS API and is exercised in manual QA
(press F4 while another app has focus). These tests cover the event-filter
logic — routing the right messages, ignoring the wrong ones.
"""
import ctypes
from ctypes import wintypes

from src.hardware.global_hotkey import _HotkeyEventFilter, WM_HOTKEY


def _make_msg(message: int, wparam: int = 0) -> wintypes.MSG:
    """Build a MSG struct and return it; callers hand its address to the filter."""
    msg = wintypes.MSG()
    msg.message = message
    msg.wParam = wparam
    return msg


def test_filter_emits_on_matching_wm_hotkey():
    """A WM_HOTKEY message with the registered hotkey id must fire the callback."""
    emitted = []
    f = _HotkeyEventFilter(hotkey_id=1, emit_fn=lambda: emitted.append(True))

    msg = _make_msg(WM_HOTKEY, wparam=1)
    handled, _ = f.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg))

    assert emitted == [True]
    assert handled is True


def test_filter_ignores_other_hotkey_ids():
    """A WM_HOTKEY whose wParam is a different registered id must not fire."""
    emitted = []
    f = _HotkeyEventFilter(hotkey_id=1, emit_fn=lambda: emitted.append(True))

    msg = _make_msg(WM_HOTKEY, wparam=99)   # someone else's hotkey
    handled, _ = f.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg))

    assert emitted == []
    assert handled is False


def test_filter_ignores_non_hotkey_messages():
    """Non-WM_HOTKEY messages must pass through without firing the callback."""
    emitted = []
    f = _HotkeyEventFilter(hotkey_id=1, emit_fn=lambda: emitted.append(True))

    msg = _make_msg(0x00FF, wparam=1)   # some other Windows message
    handled, _ = f.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg))

    assert emitted == []
    assert handled is False


def test_filter_ignores_non_windows_event_types():
    """Non-Windows event types (defensive guard) must not even touch the pointer."""
    emitted = []
    f = _HotkeyEventFilter(hotkey_id=1, emit_fn=lambda: emitted.append(True))

    # Passing a zero address under a non-Windows eventType would crash if the
    # filter tried to dereference; the eventType check must short-circuit first.
    handled, _ = f.nativeEventFilter(b"xcb_generic_event_t", 0)

    assert emitted == []
    assert handled is False
