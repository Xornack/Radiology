import pytest
from PyQt6.QtCore import Qt
from src.ui.main_window import MainWindow

def test_main_window_properties(qtbot):
    """
    Ensures the MainWindow is visible, stays on top, and is frameless.
    """
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    # Requirement 1: Visible
    assert window.isVisible()

    # Requirement 2: Flags (Stay on Top & Frameless)
    flags = window.windowFlags()
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert flags & Qt.WindowType.FramelessWindowHint
