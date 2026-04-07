import pytest
from unittest.mock import MagicMock, patch
from src.hardware.mic_listener import MicListener

def test_mic_listener_no_device_found():
    """
    Ensures that if the device is not found, MicListener handles it
    gracefully (e.g., returns False on start).
    """
    with patch('hid.device') as mock_hid:
        mock_hid.side_effect = Exception("Device not found")
        listener = MicListener(vendor_id=0x0555, product_id=0x1234)
        result = listener.start()
        assert result is False

def test_mic_listener_triggers_callback():
    """
    Mocks a HID device and ensures the callback is triggered when 
    a button press is simulated in the raw HID data.
    """
    mock_device = MagicMock()
    # Simulate a single HID report (e.g., [0, 1] means button pressed)
    mock_device.read.side_effect = [[0x00, 0x01], StopIteration] 
    
    with patch('hid.device', return_value=mock_device):
        callback_called = False
        def my_callback(state):
            nonlocal callback_called
            callback_called = True

        listener = MicListener(vendor_id=0x0555, product_id=0x1234)
        listener.on_trigger = my_callback
        
        # We manually call a single 'tick' of the listener logic
        # to avoid starting a real background thread in a unit test.
        listener._poll_once()
        
        assert callback_called is True
