from unittest.mock import patch

import numpy as np
import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QWheelEvent

from pyradstack.main_window import MainWindow


@pytest.fixture
def five_slice_dir(tmp_path):
    """Directory with 5 synthetic DICOM files, each with distinct pixel values."""
    from tests.conftest import _write_dcm_with_pixels

    for i in range(1, 6):
        pixels = np.full((64, 64), i * 40, dtype=np.int16)
        _write_dcm_with_pixels(
            tmp_path / f"img_{i:03d}.dcm",
            pixels,
            window_center=100,
            window_width=200,
            instance_number=i,
        )
    return str(tmp_path)


def _scroll_down(widget):
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
    widget.wheelEvent(event)


def _scroll_up(widget):
    event = QWheelEvent(
        QPoint(0, 0).toPointF(),
        QPoint(0, 0).toPointF(),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    widget.wheelEvent(event)


class TestEndToEnd:
    """Full pipeline: open folder → load → scroll through all slices."""

    def test_open_and_scroll_through_all_slices(self, qtbot, five_slice_dir):
        win = MainWindow()
        qtbot.addWidget(win)

        # Open the folder
        with patch("pyradstack.main_window.QFileDialog.getExistingDirectory", return_value=five_slice_dir):
            win._open_folder()

        stack = win.viewer._stack
        assert stack is not None
        assert len(stack) == 5

        # Verify first slice is displayed
        assert win.viewer.pixmap() is not None
        assert not win.viewer.pixmap().isNull()
        assert win.statusBar().currentMessage() == "Slice 1 / 5"

        # Scroll through all 5 slices, verifying each
        for expected_index in range(1, 5):
            _scroll_down(win.viewer)
            assert stack.current_slice == expected_index
            assert win.statusBar().currentMessage() == f"Slice {expected_index + 1} / 5"
            assert not win.viewer.pixmap().isNull()

        # Should be at slice 5 (index 4) now
        assert stack.current_slice == 4

        # Scroll back to the top
        for expected_index in range(3, -1, -1):
            _scroll_up(win.viewer)
            assert stack.current_slice == expected_index
            assert win.statusBar().currentMessage() == f"Slice {expected_index + 1} / 5"

        assert stack.current_slice == 0

    def test_each_slice_has_distinct_image(self, qtbot, five_slice_dir):
        win = MainWindow()
        qtbot.addWidget(win)

        with patch("pyradstack.main_window.QFileDialog.getExistingDirectory", return_value=five_slice_dir):
            win._open_folder()

        stack = win.viewer._stack
        images = [stack.get_image(i) for i in range(5)]

        # Each slice was created with different pixel values, so windowed results should differ
        for i in range(4):
            assert not np.array_equal(images[i], images[i + 1]), (
                f"Slice {i} and {i + 1} should have different pixel values"
            )

    def test_scrolling_past_bounds_stays_clamped(self, qtbot, five_slice_dir):
        win = MainWindow()
        qtbot.addWidget(win)

        with patch("pyradstack.main_window.QFileDialog.getExistingDirectory", return_value=five_slice_dir):
            win._open_folder()

        stack = win.viewer._stack

        # Scroll up past the beginning
        for _ in range(10):
            _scroll_up(win.viewer)
        assert stack.current_slice == 0
        assert win.statusBar().currentMessage() == "Slice 1 / 5"

        # Scroll down past the end
        for _ in range(20):
            _scroll_down(win.viewer)
        assert stack.current_slice == 4
        assert win.statusBar().currentMessage() == "Slice 5 / 5"
