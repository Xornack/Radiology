from PyQt6.QtWidgets import (
    QMainWindow, QTextEdit, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QPushButton,
)
from PyQt6.QtCore import Qt, QPoint


class MainWindow(QMainWindow):
    """
    Frameless floating dictation window.
    Stays on top of other applications and is draggable via the title bar.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Dictation Platform")
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint
        )
        self.resize(440, 210)
        self._drag_pos: QPoint | None = None

        # ── Root layout ──────────────────────────────────────────────────────
        root_widget = QWidget()
        root_widget.setObjectName("rootWidget")
        self.setCentralWidget(root_widget)
        root = QVBoxLayout(root_widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Title bar (draggable) ─────────────────────────────────────────────
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(34)
        title_bar.mousePressEvent = self._on_title_press
        title_bar.mouseMoveEvent = self._on_title_move

        tb = QHBoxLayout(title_bar)
        tb.setContentsMargins(10, 0, 6, 0)

        icon_label = QLabel("AI Dictation")
        icon_label.setObjectName("appTitle")
        tb.addWidget(icon_label)
        tb.addStretch()

        self.min_btn = QPushButton("\u2212")   # −
        self.min_btn.setObjectName("winBtn")
        self.min_btn.setFixedSize(26, 26)
        self.min_btn.setToolTip("Minimize")
        self.min_btn.clicked.connect(self.showMinimized)
        tb.addWidget(self.min_btn)

        self.close_btn = QPushButton("\u00d7")  # ×
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setFixedSize(26, 26)
        self.close_btn.setToolTip("Close")
        self.close_btn.clicked.connect(self.close)
        tb.addWidget(self.close_btn)

        root.addWidget(title_bar)

        # ── Status bar ────────────────────────────────────────────────────────
        self.status_label = QLabel("● Ready")
        self.status_label.setObjectName("statusLabel")
        root.addWidget(self.status_label)

        # ── Transcript editor ─────────────────────────────────────────────────
        self.editor = QTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setPlaceholderText("Dictation transcript appears here...")
        root.addWidget(self.editor)

        self._apply_styles()
        self.set_status("Ready")

    # ── Drag support ──────────────────────────────────────────────────────────

    def _on_title_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def _on_title_move(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_status(self, text: str, color: str = "#a6e3a1"):
        """Update the status pill. Default color is green (idle/done)."""
        self.status_label.setText(f"● {text}")
        self.status_label.setStyleSheet(
            f"color: {color}; padding: 2px 10px; font-size: 11px;"
        )

    def append_text(self, text: str):
        """Append a transcribed segment to the transcript display."""
        self.editor.append(text)

    # ── Styling ───────────────────────────────────────────────────────────────

    def _apply_styles(self):
        self.setStyleSheet("""
            #rootWidget {
                background: #1e1e2e;
                border: 1px solid #585b70;
                border-radius: 8px;
            }
            #titleBar {
                background: #24273a;
                border-bottom: 1px solid #45475a;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            #appTitle {
                color: #cdd6f4;
                font-size: 13px;
                font-weight: bold;
            }
            #winBtn {
                background: #313244;
                color: #cdd6f4;
                border: none;
                border-radius: 4px;
                font-size: 16px;
            }
            #winBtn:hover { background: #45475a; }
            #closeBtn {
                background: #313244;
                color: #cdd6f4;
                border: none;
                border-radius: 4px;
                font-size: 16px;
            }
            #closeBtn:hover { background: #f38ba8; color: #1e1e2e; }
            QTextEdit {
                background: #181825;
                color: #cdd6f4;
                border: none;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                padding: 6px;
            }
        """)
