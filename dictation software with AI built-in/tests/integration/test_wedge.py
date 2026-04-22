"""Wedge tests — verify SendInput batching and UTF-16 encoding of text.

The wedge uses KEYEVENTF_UNICODE for every character and batches all
key-down/key-up events into a single SendInput call. These tests confirm
the event count (2 * UTF-16 code units) and that SendInput is called once
per type_text invocation.
"""
from unittest.mock import patch
from src.engine.wedge import type_text


def test_type_text_single_bmp_char_batches_two_events():
    """A single BMP char produces one SendInput call with nInputs=2 (down+up)."""
    with patch('ctypes.windll.user32.SendInput') as mock_send_input:
        mock_send_input.return_value = 2
        type_text("h")
        assert mock_send_input.call_count == 1
        args, _ = mock_send_input.call_args_list[0]
        assert args[0] == 2   # 1 code unit × 2 events


def test_type_text_uppercase_batches_two_events():
    """Uppercase is a distinct Unicode codepoint, not Shift+lower — still 2 events."""
    with patch('ctypes.windll.user32.SendInput') as mock_send_input:
        mock_send_input.return_value = 2
        type_text("H")
        assert mock_send_input.call_count == 1
        args, _ = mock_send_input.call_args_list[0]
        assert args[0] == 2


def test_type_text_shifted_punctuation_batches_two_events():
    """'!' no longer requires Shift emulation — a single Unicode codepoint."""
    with patch('ctypes.windll.user32.SendInput') as mock_send_input:
        mock_send_input.return_value = 2
        type_text("!")
        assert mock_send_input.call_count == 1
        args, _ = mock_send_input.call_args_list[0]
        assert args[0] == 2


def test_type_text_mixed_case_two_chars_batches_four_events():
    """Two BMP chars produce one SendInput call with nInputs=4."""
    with patch('ctypes.windll.user32.SendInput') as mock_send_input:
        mock_send_input.return_value = 4
        type_text("Hi")
        assert mock_send_input.call_count == 1
        args, _ = mock_send_input.call_args_list[0]
        assert args[0] == 4


def test_type_text_preserves_case_in_batch():
    """'Hi!' is 3 BMP chars, all Unicode — single batch of 6 events."""
    with patch('ctypes.windll.user32.SendInput') as mock_send_input:
        mock_send_input.return_value = 6
        type_text("Hi!")
        assert mock_send_input.call_count == 1
        args, _ = mock_send_input.call_args_list[0]
        assert args[0] == 6


def test_type_text_colon_and_question_no_shift_emulation():
    """':' and '?' are direct Unicode codepoints — 2 events each, not 4."""
    with patch('ctypes.windll.user32.SendInput') as mock_send_input:
        mock_send_input.return_value = 2
        type_text(":")
        assert mock_send_input.call_count == 1
        assert mock_send_input.call_args_list[0][0][0] == 2

    with patch('ctypes.windll.user32.SendInput') as mock_send_input:
        mock_send_input.return_value = 2
        type_text("?")
        assert mock_send_input.call_count == 1
        assert mock_send_input.call_args_list[0][0][0] == 2


def test_type_text_supplementary_plane_char_uses_surrogate_pair():
    """Codepoints above U+FFFF (e.g. U+1F600 😀) need a UTF-16 surrogate pair,
    so one Python character becomes two code units = 4 events."""
    with patch('ctypes.windll.user32.SendInput') as mock_send_input:
        mock_send_input.return_value = 4
        type_text("\U0001F600")   # grinning face
        assert mock_send_input.call_count == 1
        args, _ = mock_send_input.call_args_list[0]
        assert args[0] == 4


def test_type_text_empty_string_is_noop():
    """Empty input must skip the SendInput call entirely (no zero-size buffers)."""
    with patch('ctypes.windll.user32.SendInput') as mock_send_input:
        type_text("")
        assert mock_send_input.call_count == 0
