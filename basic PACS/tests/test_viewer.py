import numpy as np
import pytest
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QMouseEvent, QWheelEvent
from PyQt6.QtWidgets import QApplication

from pyradstack.stack import ImageStack
from pyradstack.viewer import ViewerWidget


@pytest.fixture
def dicom_stack(tmp_path):
    """Five-slice DICOM stack for viewer tests."""
    from tests.conftest import _write_dcm_with_pixels

    paths = []
    for i in range(1, 6):
        pixels = np.full((64, 64), i * 10, dtype=np.int16)
        path = _write_dcm_with_pixels(
            tmp_path / f"slice_{i}.dcm",
            pixels,
            window_center=50,
            window_width=100,
            instance_number=i,
        )
        paths.append(path)
    return ImageStack(paths)


class TestViewerInstantiation:
    def test_can_create_viewer(self, qtbot):
        widget = ViewerWidget()
        qtbot.addWidget(widget)
        assert widget is not None

    def test_viewer_has_default_size(self, qtbot):
        widget = ViewerWidget()
        qtbot.addWidget(widget)
        assert widget.minimumWidth() > 0
        assert widget.minimumHeight() > 0


class TestViewerDisplay:
    def test_set_stack_shows_first_slice(self, qtbot, dicom_stack):
        widget = ViewerWidget()
        qtbot.addWidget(widget)
        widget.set_stack(dicom_stack)
        assert widget.pixmap() is not None
        assert not widget.pixmap().isNull()

    def test_displayed_image_dimensions(self, qtbot, dicom_stack):
        widget = ViewerWidget()
        qtbot.addWidget(widget)
        widget.set_stack(dicom_stack)
        pixmap = widget.pixmap()
        assert pixmap.width() == 64
        assert pixmap.height() == 64

    def test_no_stack_means_no_pixmap(self, qtbot):
        widget = ViewerWidget()
        qtbot.addWidget(widget)
        assert widget.pixmap() is None or widget.pixmap().isNull()


class TestViewerScrolling:
    def _wheel_event(self, delta):
        """Create a wheel event with the given vertical delta."""
        return QWheelEvent(
            QPoint(0, 0).toPointF(),       # pos
            QPoint(0, 0).toPointF(),       # globalPos
            QPoint(0, 0),                  # pixelDelta
            QPoint(0, delta),              # angleDelta
            Qt.MouseButton.NoButton,       # buttons
            Qt.KeyboardModifier.NoModifier,  # modifiers
            Qt.ScrollPhase.NoScrollPhase,  # phase
            False,                         # inverted
        )

    def test_wheel_down_advances_slice(self, qtbot, dicom_stack):
        widget = ViewerWidget()
        qtbot.addWidget(widget)
        widget.set_stack(dicom_stack)
        assert dicom_stack.current_slice == 0

        widget.wheelEvent(self._wheel_event(-120))
        assert dicom_stack.current_slice == 1

    def test_wheel_up_goes_back(self, qtbot, dicom_stack):
        widget = ViewerWidget()
        qtbot.addWidget(widget)
        widget.set_stack(dicom_stack)
        dicom_stack.set_slice(3)
        widget._display_current_slice()

        widget.wheelEvent(self._wheel_event(120))
        assert dicom_stack.current_slice == 2

    def test_wheel_clamps_at_bounds(self, qtbot, dicom_stack):
        widget = ViewerWidget()
        qtbot.addWidget(widget)
        widget.set_stack(dicom_stack)

        # scroll up past beginning
        for _ in range(5):
            widget.wheelEvent(self._wheel_event(120))
        assert dicom_stack.current_slice == 0

        # scroll down past end
        for _ in range(20):
            widget.wheelEvent(self._wheel_event(-120))
        assert dicom_stack.current_slice == 4


def _mouse_event(event_type, pos, button, buttons):
    """Helper to create a QMouseEvent."""
    return QMouseEvent(
        event_type,
        QPointF(pos[0], pos[1]),
        QPointF(pos[0], pos[1]),
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )


class TestLeftClickDragScroll:
    """Left-click drag up/down scrolls through slices."""

    def test_drag_down_advances_slices(self, qtbot, dicom_stack):
        widget = ViewerWidget()
        qtbot.addWidget(widget)
        widget.set_stack(dicom_stack)
        assert dicom_stack.current_slice == 0

        # press at y=100, drag to y=150 (down = next slice)
        widget.mousePressEvent(_mouse_event(
            QMouseEvent.Type.MouseButtonPress, (100, 100),
            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        ))
        widget.mouseMoveEvent(_mouse_event(
            QMouseEvent.Type.MouseMove, (100, 150),
            Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
        ))
        assert dicom_stack.current_slice > 0

    def test_drag_up_goes_back(self, qtbot, dicom_stack):
        widget = ViewerWidget()
        qtbot.addWidget(widget)
        widget.set_stack(dicom_stack)
        dicom_stack.set_slice(3)
        widget._display_current_slice()

        widget.mousePressEvent(_mouse_event(
            QMouseEvent.Type.MouseButtonPress, (100, 150),
            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        ))
        widget.mouseMoveEvent(_mouse_event(
            QMouseEvent.Type.MouseMove, (100, 100),
            Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
        ))
        assert dicom_stack.current_slice < 3

    def test_drag_clamps_at_bounds(self, qtbot, dicom_stack):
        widget = ViewerWidget()
        qtbot.addWidget(widget)
        widget.set_stack(dicom_stack)

        # drag way up from slice 0
        widget.mousePressEvent(_mouse_event(
            QMouseEvent.Type.MouseButtonPress, (100, 200),
            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        ))
        widget.mouseMoveEvent(_mouse_event(
            QMouseEvent.Type.MouseMove, (100, 0),
            Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
        ))
        assert dicom_stack.current_slice == 0

    def test_incremental_moves_accumulate(self, qtbot, dicom_stack):
        """Many small mouse moves (like real events) still scroll."""
        widget = ViewerWidget()
        qtbot.addWidget(widget)
        widget.set_stack(dicom_stack)
        assert dicom_stack.current_slice == 0

        widget.mousePressEvent(_mouse_event(
            QMouseEvent.Type.MouseButtonPress, (100, 100),
            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        ))
        # simulate 5 small 2px moves = 10px total = 1 slice
        for i in range(1, 6):
            widget.mouseMoveEvent(_mouse_event(
                QMouseEvent.Type.MouseMove, (100, 100 + i * 2),
                Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
            ))
        assert dicom_stack.current_slice == 1

    def test_release_stops_scrolling(self, qtbot, dicom_stack):
        widget = ViewerWidget()
        qtbot.addWidget(widget)
        widget.set_stack(dicom_stack)

        widget.mousePressEvent(_mouse_event(
            QMouseEvent.Type.MouseButtonPress, (100, 100),
            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        ))
        widget.mouseReleaseEvent(_mouse_event(
            QMouseEvent.Type.MouseButtonRelease, (100, 100),
            Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton,
        ))
        # move after release should not scroll
        widget.mouseMoveEvent(_mouse_event(
            QMouseEvent.Type.MouseMove, (100, 200),
            Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
        ))
        assert dicom_stack.current_slice == 0


class TestBothButtonsWindowLevel:
    """Left+Right mouse buttons drag adjusts W/L."""

    BOTH = Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton

    def test_horizontal_drag_changes_width(self, qtbot, dicom_stack):
        widget = ViewerWidget()
        qtbot.addWidget(widget)
        widget.set_stack(dicom_stack)

        # press both buttons
        widget.mousePressEvent(_mouse_event(
            QMouseEvent.Type.MouseButtonPress, (100, 100),
            Qt.MouseButton.LeftButton, self.BOTH,
        ))
        # drag right
        widget.mouseMoveEvent(_mouse_event(
            QMouseEvent.Type.MouseMove, (160, 100),
            Qt.MouseButton.NoButton, self.BOTH,
        ))
        assert dicom_stack.window_width is not None
        assert dicom_stack.window_width > 100  # original was 100

    def test_vertical_drag_changes_center(self, qtbot, dicom_stack):
        widget = ViewerWidget()
        qtbot.addWidget(widget)
        widget.set_stack(dicom_stack)

        widget.mousePressEvent(_mouse_event(
            QMouseEvent.Type.MouseButtonPress, (100, 100),
            Qt.MouseButton.LeftButton, self.BOTH,
        ))
        # drag down (increase y = increase center)
        widget.mouseMoveEvent(_mouse_event(
            QMouseEvent.Type.MouseMove, (100, 160),
            Qt.MouseButton.NoButton, self.BOTH,
        ))
        assert dicom_stack.window_center is not None
        assert dicom_stack.window_center > 50  # original was 50

    def test_wl_drag_does_not_scroll(self, qtbot, dicom_stack):
        widget = ViewerWidget()
        qtbot.addWidget(widget)
        widget.set_stack(dicom_stack)

        widget.mousePressEvent(_mouse_event(
            QMouseEvent.Type.MouseButtonPress, (100, 100),
            Qt.MouseButton.LeftButton, self.BOTH,
        ))
        widget.mouseMoveEvent(_mouse_event(
            QMouseEvent.Type.MouseMove, (100, 200),
            Qt.MouseButton.NoButton, self.BOTH,
        ))
        assert dicom_stack.current_slice == 0

    def test_width_does_not_go_below_one(self, qtbot, dicom_stack):
        widget = ViewerWidget()
        qtbot.addWidget(widget)
        widget.set_stack(dicom_stack)

        widget.mousePressEvent(_mouse_event(
            QMouseEvent.Type.MouseButtonPress, (200, 100),
            Qt.MouseButton.LeftButton, self.BOTH,
        ))
        # drag far left to try to make width negative
        widget.mouseMoveEvent(_mouse_event(
            QMouseEvent.Type.MouseMove, (0, 100),
            Qt.MouseButton.NoButton, self.BOTH,
        ))
        assert dicom_stack.window_width >= 1
