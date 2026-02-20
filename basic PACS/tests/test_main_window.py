from unittest.mock import patch, MagicMock

import numpy as np
import pytest

from pyradstack.main_window import MainWindow


@pytest.fixture
def dicom_dir(tmp_path):
    """Directory with 3 DICOM files for open-folder tests."""
    from tests.conftest import _write_dcm_with_pixels

    for i in range(1, 4):
        pixels = np.full((32, 32), i * 20, dtype=np.int16)
        _write_dcm_with_pixels(
            tmp_path / f"img_{i}.dcm",
            pixels,
            window_center=40,
            window_width=80,
            instance_number=i,
        )
    return str(tmp_path)


class TestMainWindowCreation:
    def test_opens_without_error(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        assert win is not None

    def test_has_file_menu(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        menu_bar = win.menuBar()
        actions = [a.text() for a in menu_bar.actions()]
        assert any("File" in a for a in actions)

    def test_file_menu_has_open_folder(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)
        file_menu = None
        for action in win.menuBar().actions():
            if "File" in action.text():
                file_menu = action.menu()
                break
        assert file_menu is not None
        action_texts = [a.text() for a in file_menu.actions()]
        assert any("Open Folder" in t for t in action_texts)


class TestOpenFolder:
    def test_open_folder_loads_stack_into_viewer(self, qtbot, dicom_dir):
        win = MainWindow()
        qtbot.addWidget(win)

        with patch("pyradstack.main_window.QFileDialog.getExistingDirectory", return_value=dicom_dir):
            win._open_folder()

        assert win.viewer._stack is not None
        assert len(win.viewer._stack) == 3

    def test_open_folder_cancelled_does_nothing(self, qtbot):
        win = MainWindow()
        qtbot.addWidget(win)

        with patch("pyradstack.main_window.QFileDialog.getExistingDirectory", return_value=""):
            win._open_folder()

        assert win.viewer._stack is None

    def test_open_folder_displays_first_slice(self, qtbot, dicom_dir):
        win = MainWindow()
        qtbot.addWidget(win)

        with patch("pyradstack.main_window.QFileDialog.getExistingDirectory", return_value=dicom_dir):
            win._open_folder()

        assert win.viewer.pixmap() is not None
        assert not win.viewer.pixmap().isNull()


class TestStatusBar:
    def test_shows_slice_info_after_load(self, qtbot, dicom_dir):
        win = MainWindow()
        qtbot.addWidget(win)

        with patch("pyradstack.main_window.QFileDialog.getExistingDirectory", return_value=dicom_dir):
            win._open_folder()

        text = win.statusBar().currentMessage()
        assert "Slice 1 / 3" in text

    def test_status_updates_on_scroll(self, qtbot, dicom_dir):
        from PyQt6.QtCore import QPoint, Qt
        from PyQt6.QtGui import QWheelEvent

        win = MainWindow()
        qtbot.addWidget(win)

        with patch("pyradstack.main_window.QFileDialog.getExistingDirectory", return_value=dicom_dir):
            win._open_folder()

        # scroll down one slice
        event = QWheelEvent(
            QPoint(0, 0).toPointF(),
            QPoint(0, 0).toPointF(),
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        win.viewer.wheelEvent(event)

        text = win.statusBar().currentMessage()
        assert "Slice 2 / 3" in text
