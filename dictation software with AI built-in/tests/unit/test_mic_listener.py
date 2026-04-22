import time
import pytest
from unittest.mock import MagicMock, patch
from src.hardware.mic_listener import MicListener


def test_mic_listener_no_device_found():
    """If the HID device cannot be opened, start() must return False gracefully."""
    with patch('hid.device') as mock_hid:
        mock_hid.side_effect = Exception("Device not found")
        listener = MicListener(vendor_id=0x0555, product_id=0x1234)
        result = listener.start()
        assert result is False


def test_mic_listener_triggers_callback(qtbot):
    """Signal must fire when a button-press HID report is detected."""
    mock_device = MagicMock()
    mock_device.read.return_value = [0x00, 0x01]  # Non-zero byte = pressed

    received: list[bool] = []
    listener = MicListener(vendor_id=0x0555, product_id=0x1234)
    listener.device = mock_device   # Inject mock device directly
    listener.trigger_changed.connect(received.append)

    listener._poll_once()

    assert received == [True]


def test_mic_listener_callback_fires_on_state_change_only(qtbot):
    """Signal must only fire when the button state changes, not on every poll."""
    mock_device = MagicMock()
    mock_device.read.return_value = [0x00, 0x01]  # Always pressed

    received: list[bool] = []
    listener = MicListener(vendor_id=0x0555, product_id=0x1234)
    listener.device = mock_device
    listener.trigger_changed.connect(received.append)

    listener._poll_once()  # State: False -> True  (fires)
    listener._poll_once()  # State: True -> True   (no change, no fire)
    listener._poll_once()  # State: True -> True   (no change, no fire)

    assert received == [True]


def test_mic_listener_starts_polling_thread():
    """start() must spawn a live daemon polling thread."""
    mock_device = MagicMock()
    mock_device.read.return_value = []  # No button data — prevents callback noise

    with patch('hid.device', return_value=mock_device):
        listener = MicListener(vendor_id=0x0555, product_id=0x1234)
        result = listener.start()

        assert result is True
        assert listener._thread is not None
        assert listener._thread.is_alive()

        listener.stop()
        listener._thread.join(timeout=1.0)
        assert not listener._thread.is_alive()


def test_mic_listener_emits_trigger_changed_signal(qtbot):
    """The Qt signal trigger_changed must fire when the button state changes.

    This is the signal that `main.py` actually connects to — the HID polling
    thread emits, Qt queues it to the GUI thread, handle_trigger runs safely.
    """
    mock_device = MagicMock()
    mock_device.read.return_value = [0x00, 0x01]

    listener = MicListener(vendor_id=0x0555, product_id=0x1234)
    listener.device = mock_device

    received = []
    listener.trigger_changed.connect(lambda pressed: received.append(pressed))

    listener._poll_once()   # False -> True (fires)
    listener._poll_once()   # True -> True  (no change, no fire)

    assert received == [True]


def test_mic_listener_stop_cleans_up():
    """stop() must close the HID device and reset internal state."""
    mock_device = MagicMock()
    mock_device.read.return_value = []

    with patch('hid.device', return_value=mock_device):
        listener = MicListener(vendor_id=0x0555, product_id=0x1234)
        listener.start()
        listener.stop()

        mock_device.close.assert_called_once()
        assert listener.device is None
