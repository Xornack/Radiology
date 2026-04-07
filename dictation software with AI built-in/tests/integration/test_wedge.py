import pytest
from unittest.mock import patch, MagicMock
from src.engine.wedge import type_text

def test_type_text_calls_win32_api():
    """
    Verifies that type_text correctly calculates and sends 
    Win32 SendInput calls with scan codes.
    """
    with patch('ctypes.windll.user32.SendInput') as mock_send_input:
        # Mocking the SendInput return value (number of events processed)
        mock_send_input.return_value = 1
        
        test_string = "h"
        type_text(test_string)
        
        # 'h' should result in 2 calls: Press and Release
        assert mock_send_input.call_count == 2
        
        # Verify the first call (Press)
        # The second argument is the pointer to the INPUT structure
        # We check the count of inputs sent (first argument)
        args, kwargs = mock_send_input.call_args_list[0]
        assert args[0] == 1 # nInputs
