import pytest
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


def test_close_button_hides_window(qtbot):
    """Clicking the × button must close the window."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    assert window.isVisible()

    window.close_btn.click()
    assert not window.isVisible()


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
