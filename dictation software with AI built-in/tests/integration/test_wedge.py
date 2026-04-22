"""Wedge tests — verify PostMessageW(WM_CHAR) delivery and UTF-16 encoding.

The wedge posts one WM_CHAR message per UTF-16 code unit to the focused
child of the foreground window. These tests confirm the call count matches
the code-unit count and that the correct message + code unit are posted.
"""
from unittest.mock import patch
from src.engine.wedge import type_text, WM_CHAR


def _patches():
    """Patch the Win32 shims so no real windows are touched during tests."""
    return (
        patch('src.engine.wedge._focused_hwnd', return_value=0xDEAD),
        patch('src.engine.wedge._user32.PostMessageW', return_value=1),
    )


def test_type_text_single_bmp_char_one_post():
    focused_patch, post_patch = _patches()
    with focused_patch, post_patch as mock_post:
        type_text("h")
        assert mock_post.call_count == 1
        args, _ = mock_post.call_args_list[0]
        assert args[0] == 0xDEAD
        assert args[1] == WM_CHAR
        assert args[2] == ord("h")
        assert args[3] == 0


def test_type_text_uppercase_one_post():
    focused_patch, post_patch = _patches()
    with focused_patch, post_patch as mock_post:
        type_text("H")
        assert mock_post.call_count == 1
        assert mock_post.call_args_list[0][0][2] == ord("H")


def test_type_text_punctuation_one_post_each():
    focused_patch, post_patch = _patches()
    with focused_patch, post_patch as mock_post:
        type_text("!")
        assert mock_post.call_count == 1
        assert mock_post.call_args_list[0][0][2] == ord("!")


def test_type_text_two_chars_two_posts():
    focused_patch, post_patch = _patches()
    with focused_patch, post_patch as mock_post:
        type_text("Hi")
        assert mock_post.call_count == 2
        assert [c[0][2] for c in mock_post.call_args_list] == [ord("H"), ord("i")]


def test_type_text_three_chars_three_posts_in_order():
    focused_patch, post_patch = _patches()
    with focused_patch, post_patch as mock_post:
        type_text("Hi!")
        assert mock_post.call_count == 3
        assert [c[0][2] for c in mock_post.call_args_list] == [
            ord("H"), ord("i"), ord("!"),
        ]


def test_type_text_colon_and_question_no_shift_emulation():
    focused_patch, post_patch = _patches()
    with focused_patch, post_patch as mock_post:
        type_text(":")
        assert mock_post.call_count == 1
        assert mock_post.call_args_list[0][0][2] == ord(":")

    focused_patch, post_patch = _patches()
    with focused_patch, post_patch as mock_post:
        type_text("?")
        assert mock_post.call_count == 1
        assert mock_post.call_args_list[0][0][2] == ord("?")


def test_type_text_supplementary_plane_char_uses_surrogate_pair():
    """A U+1F600 😀 codepoint becomes 2 UTF-16 code units = 2 posts."""
    focused_patch, post_patch = _patches()
    with focused_patch, post_patch as mock_post:
        type_text("\U0001F600")
        assert mock_post.call_count == 2
        units = [c[0][2] for c in mock_post.call_args_list]
        assert 0xD800 <= units[0] <= 0xDBFF   # high surrogate
        assert 0xDC00 <= units[1] <= 0xDFFF   # low surrogate


def test_type_text_empty_string_is_noop():
    focused_patch, post_patch = _patches()
    with focused_patch, post_patch as mock_post:
        type_text("")
        assert mock_post.call_count == 0


def test_type_text_aborts_on_post_failure():
    """PostMessageW returning 0 aborts the remaining characters."""
    focused_patch = patch('src.engine.wedge._focused_hwnd', return_value=0xDEAD)
    post_patch = patch('src.engine.wedge._user32.PostMessageW')
    with focused_patch, post_patch as mock_post:
        mock_post.side_effect = [1, 0, 1, 1, 1]
        type_text("Hello")
        assert mock_post.call_count == 2


def test_type_text_noop_when_no_focused_window():
    """If there's no foreground/focused window, abort without posting."""
    focused_patch = patch('src.engine.wedge._focused_hwnd', return_value=0)
    post_patch = patch('src.engine.wedge._user32.PostMessageW')
    with focused_patch, post_patch as mock_post:
        type_text("hi")
        assert mock_post.call_count == 0
