from pathlib import Path

from PyQt6.QtGui import QAction, QWheelEvent
from PyQt6.QtWidgets import QFileDialog, QMainWindow

from pyradstack.loader import scan_directory
from pyradstack.sorting import sort_files
from pyradstack.stack import ImageStack
from pyradstack.viewer import ViewerWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyRadStack")
        self.resize(800, 600)

        self.viewer = _NotifyingViewer(self)
        self.setCentralWidget(self.viewer)

        self._build_menu()

    def _build_menu(self):
        file_menu = self.menuBar().addMenu("File")
        open_action = QAction("Open Folder...", self)
        open_action.triggered.connect(self._open_folder)
        file_menu.addAction(open_action)

    def _open_folder(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Image Folder")
        if not directory:
            return

        paths = scan_directory(Path(directory))
        sorted_paths = sort_files(paths)
        stack = ImageStack(sorted_paths)
        self.viewer.set_stack(stack)
        self._update_status()

    def _update_status(self):
        if self.viewer._stack is None:
            return
        current = self.viewer._stack.current_slice + 1
        total = len(self.viewer._stack)
        self.statusBar().showMessage(f"Slice {current} / {total}")


class _NotifyingViewer(ViewerWidget):
    """ViewerWidget subclass that notifies the MainWindow on scroll."""

    def wheelEvent(self, event: QWheelEvent) -> None:
        super().wheelEvent(event)
        parent = self.parent()
        if isinstance(parent, MainWindow):
            parent._update_status()
