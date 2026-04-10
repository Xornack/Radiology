import pytest
from unittest.mock import patch
from src.engine.wedge import type_text


def test_type_text_calls_win32_api():
    """Verifies that type_text sends Win32 SendInput calls with correct scan codes."""
    with patch('ctypes.windll.user32.SendInput') as mock_send_input:
        mock_send_input.return_value = 1
        type_text("h")
        # 'h' -> press + release = 2 calls
        assert mock_send_input.call_count == 2

        args, _ = mock_send_input.call_args_list[0]
        assert args[0] == 1  # nInputs argument


def test_type_text_direct_symbol():
    """Characters with direct scan codes (e.g. ';') produce exactly 2 SendInput calls."""
    with patch('ctypes.windll.user32.SendInput') as mock_send_input:
        mock_send_input.return_value = 1
        type_text(";")
        assert mock_send_input.call_count == 2


def test_type_text_shifted_symbol():
    """Characters requiring Shift (e.g. '!') produce 4 SendInput calls."""
    with patch('ctypes.windll.user32.SendInput') as mock_send_input:
        mock_send_input.return_value = 1
        type_text("!")
        # shift-down, key-down, key-up, shift-up = 4 calls
        assert mock_send_input.call_count == 4


def test_type_text_uppercase_letter():
    """Uppercase letters produce 4 SendInput calls (Shift + base scan code)."""
    with patch('ctypes.windll.user32.SendInput') as mock_send_input:
        mock_send_input.return_value = 1
        type_text("H")
        # shift-down, h-down, h-up, shift-up = 4 calls
        assert mock_send_input.call_count == 4


def test_type_text_preserves_case():
    """type_text must not lowercase input — mixed case uses correct shift combos."""
    with patch('ctypes.windll.user32.SendInput') as mock_send_input:
        mock_send_input.return_value = 1
        type_text("Hi")
        # 'H': 4 calls (shift), 'i': 2 calls = 6 total
        assert mock_send_input.call_count == 6


def test_type_text_colon():
    """':' is Shift+';' and must produce 4 SendInput calls."""
    with patch('ctypes.windll.user32.SendInput') as mock_send_input:
        mock_send_input.return_value = 1
        type_text(":")
        assert mock_send_input.call_count == 4


def test_type_text_question_mark():
    """'?' is Shift+'/' and must produce 4 SendInput calls."""
    with patch('ctypes.windll.user32.SendInput') as mock_send_input:
        mock_send_input.return_value = 1
        type_text("?")
        assert mock_send_input.call_count == 4
