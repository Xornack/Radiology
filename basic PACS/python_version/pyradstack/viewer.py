import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QMouseEvent, QPixmap, QWheelEvent
from PyQt6.QtWidgets import QLabel

from pyradstack.stack import ImageStack

# Pixels of mouse drag per slice when scrolling via left-click drag
_DRAG_SCROLL_SENSITIVITY = 10

# Pixels of mouse drag per W/L unit change
_WL_SENSITIVITY = 3.0


class ViewerWidget(QLabel):
    """Displays image slices from an ImageStack with mouse-wheel scrolling,
    left-click drag scrolling, and both-button W/L adjustment."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stack: ImageStack | None = None
        self.setMinimumSize(256, 256)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._last_pos: tuple[float, float] | None = None
        self._buttons: Qt.MouseButton = Qt.MouseButton.NoButton
        self._drag_accum: float = 0.0
        self._wl_base_center: float = 128
        self._wl_base_width: float = 256

    def set_stack(self, stack: ImageStack) -> None:
        self._stack = stack
        self._stack.set_slice(0)
        self._init_wl_from_stack()
        self._display_current_slice()

    def _init_wl_from_stack(self) -> None:
        """Read initial W/L from the first DICOM slice's tags."""
        if self._stack is None or len(self._stack) == 0:
            return
        import pydicom
        path = self._stack[0]
        if path.suffix.lower() == ".dcm":
            try:
                ds = pydicom.dcmread(str(path), stop_before_pixels=True, force=True)
                self._wl_base_center = float(getattr(ds, "WindowCenter", 128))
                self._wl_base_width = float(getattr(ds, "WindowWidth", 256))
            except Exception:
                pass

    def _display_current_slice(self) -> None:
        if self._stack is None or len(self._stack) == 0:
            return

        img_array = self._stack.get_image(self._stack.current_slice)
        height, width = img_array.shape
        bytes_per_line = width

        qimage = QImage(
            img_array.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_Grayscale8,
        )
        self.setPixmap(QPixmap.fromImage(qimage))

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._stack is None:
            return

        delta = event.angleDelta().y()
        if delta < 0:
            self._stack.next_slice()
        elif delta > 0:
            self._stack.prev_slice()

        self._display_current_slice()
        event.accept()

    # --- Mouse press / move / release ---

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._buttons = event.buttons()
        self._last_pos = (event.position().x(), event.position().y())
        self._drag_accum = 0.0
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._buttons = event.buttons()
        if self._buttons == Qt.MouseButton.NoButton:
            self._last_pos = None
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._stack is None or self._last_pos is None:
            return

        x, y = event.position().x(), event.position().y()
        dx = x - self._last_pos[0]
        dy = y - self._last_pos[1]
        self._last_pos = (x, y)

        buttons = event.buttons()
        both = Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton
        if (buttons & both) == both:
            self._handle_wl_drag(dx, dy)
        elif buttons & Qt.MouseButton.LeftButton:
            self._handle_scroll_drag(dy)

        event.accept()

    def _handle_scroll_drag(self, dy: float) -> None:
        """Left-click drag: scroll slices based on accumulated vertical movement."""
        self._drag_accum += dy
        steps = int(self._drag_accum / _DRAG_SCROLL_SENSITIVITY)
        if steps == 0:
            return
        self._drag_accum -= steps * _DRAG_SCROLL_SENSITIVITY
        for _ in range(abs(steps)):
            if steps > 0:
                self._stack.next_slice()
            else:
                self._stack.prev_slice()
        self._display_current_slice()

    def _handle_wl_drag(self, dx: float, dy: float) -> None:
        """Both buttons drag: dx = window width, dy = window center."""
        current_center = self._stack.window_center if self._stack.window_center is not None else self._wl_base_center
        current_width = self._stack.window_width if self._stack.window_width is not None else self._wl_base_width

        new_width = max(1.0, current_width + dx * _WL_SENSITIVITY)
        new_center = current_center + dy * _WL_SENSITIVITY  # drag down = increase center

        self._stack.window_width = new_width
        self._stack.window_center = new_center
        self._display_current_slice()
