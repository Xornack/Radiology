import pytest
from unittest.mock import patch
from PyQt6.QtCore import Qt
from src.ui.main_window import MainWindow


def test_main_window_properties(qtbot):
    """Window must be visible, stay on top, and be frameless."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.isVisible()
    flags = window.windowFlags()
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert flags & Qt.WindowType.FramelessWindowHint


def test_close_button_quits_application(qtbot):
    """Clicking × must terminate the application, not just hide the window."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    with patch("src.ui.main_window.QApplication.instance") as mock_instance:
        window.close_btn.click()
        mock_instance.return_value.quit.assert_called_once()


def test_minimize_button_exists(qtbot):
    """A minimize button must be present."""
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.min_btn is not None


def test_set_status_updates_label(qtbot):
    """set_status() must update the status label text."""
    window = MainWindow()
    qtbot.addWidget(window)

    window.set_status("Recording...")
    assert "Recording..." in window.status_label.text()


def test_set_status_default_ready(qtbot):
    """Status label must start in the Ready state."""
    window = MainWindow()
    qtbot.addWidget(window)
    assert "Ready" in window.status_label.text()


def test_append_text_adds_to_editor(qtbot):
    """append_text() must add content to the transcript editor."""
    window = MainWindow()
    qtbot.addWidget(window)

    window.append_text("No acute cardiopulmonary findings.")
    assert "No acute cardiopulmonary findings." in window.editor.toPlainText()


def test_refresh_button_fires_callback(qtbot):
    """Clicking the refresh button must invoke on_refresh_devices."""
    window = MainWindow()
    qtbot.addWidget(window)

    calls = []
    window.on_refresh_devices = lambda: calls.append(True)
    window.refresh_btn.click()

    assert calls == [True]


def test_refresh_button_without_callback_is_safe(qtbot):
    """Clicking refresh with no handler wired must not raise."""
    window = MainWindow()
    qtbot.addWidget(window)
    # on_refresh_devices defaults to None — click must be a no-op
    window.refresh_btn.click()


def test_refresh_button_disabled_while_recording(qtbot):
    """Refresh must be locked during active recording, like the mic combo."""
    window = MainWindow()
    qtbot.addWidget(window)

    window.set_recording_state(True)
    assert not window.refresh_btn.isEnabled()

    window.set_recording_state(False)
    assert window.refresh_btn.isEnabled()


def test_populate_microphones_preserves_selection(qtbot):
    """Re-populating with the same selected_index must keep that device selected."""
    window = MainWindow()
    qtbot.addWidget(window)

    devices = [
        {"index": 1, "name": "Mic A", "hostapi_name": "MME", "is_default": False},
        {"index": 2, "name": "Mic B", "hostapi_name": "MME", "is_default": True},
    ]
    window.populate_microphones(devices, selected_index=2)
    assert window.mic_combo.currentData() == 2

    # Simulate a refresh that adds a new device — selection must persist.
    devices.append({"index": 3, "name": "New Mic", "hostapi_name": "WASAPI", "is_default": False})
    window.populate_microphones(devices, selected_index=2)
    assert window.mic_combo.currentData() == 2
