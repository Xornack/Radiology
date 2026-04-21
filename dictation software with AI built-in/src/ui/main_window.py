from typing import Callable, Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QPushButton, QComboBox,
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor


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
        self.resize(460, 310)
        self._drag_pos: Optional[QPoint] = None
        # Hooks set by main.py. `on_toggle_recording` is called with True/False
        # when the Record/Stop buttons are clicked. `on_mic_changed` fires when
        # the user picks a different microphone from the dropdown.
        self.on_generate_impression: Optional[Callable[[], None]] = None
        self.on_toggle_recording: Optional[Callable[[bool], None]] = None
        self.on_mic_changed: Optional[Callable[[Optional[int]], None]] = None
        self.on_refresh_devices: Optional[Callable[[], None]] = None

        # Cursor position where the current streaming partial begins.
        # -1 means no active streaming session.
        self._partial_start: int = -1

        # Root layout
        root_widget = QWidget()
        root_widget.setObjectName("rootWidget")
        self.setCentralWidget(root_widget)
        root = QVBoxLayout(root_widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Title bar (draggable)
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

        # Status bar
        self.status_label = QLabel("● Ready")
        self.status_label.setObjectName("statusLabel")
        root.addWidget(self.status_label)

        # Microphone selector
        mic_row = QWidget()
        mic_row.setObjectName("micRow")
        mr = QHBoxLayout(mic_row)
        mr.setContentsMargins(10, 4, 10, 4)
        mr.setSpacing(6)

        mic_label = QLabel("Mic:")
        mic_label.setObjectName("micLabel")
        mr.addWidget(mic_label)

        self.mic_combo = QComboBox()
        self.mic_combo.setObjectName("micCombo")
        self.mic_combo.setToolTip("Select the audio input device")
        self.mic_combo.currentIndexChanged.connect(self._on_mic_combo_changed)
        mr.addWidget(self.mic_combo, stretch=1)

        self.refresh_btn = QPushButton("↻")   # ↻
        self.refresh_btn.setObjectName("refreshBtn")
        self.refresh_btn.setFixedSize(26, 26)
        self.refresh_btn.setToolTip("Refresh device list")
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)
        mr.addWidget(self.refresh_btn)

        root.addWidget(mic_row)

        # Transcript editor
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Dictation transcript appears here...")
        root.addWidget(self.editor)

        # Action bar
        action_bar = QWidget()
        action_bar.setObjectName("actionBar")
        ab = QHBoxLayout(action_bar)
        ab.setContentsMargins(8, 6, 8, 8)
        ab.setSpacing(6)

        self.record_btn = QPushButton("● Record")
        self.record_btn.setObjectName("recordBtn")
        self.record_btn.setToolTip("Start recording (F4)")
        self.record_btn.clicked.connect(self._on_record_clicked)
        ab.addWidget(self.record_btn)

        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setToolTip("Stop recording (F4)")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        ab.addWidget(self.stop_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.setToolTip("Clear the transcript")
        self.clear_btn.clicked.connect(self.editor.clear)
        ab.addWidget(self.clear_btn)

        ab.addStretch()

        self.impression_btn = QPushButton("Generate Impression")
        self.impression_btn.setObjectName("impressionBtn")
        self.impression_btn.setToolTip("Summarize the findings into an impression")
        self.impression_btn.clicked.connect(self._on_impression_clicked)
        ab.addWidget(self.impression_btn)

        root.addWidget(action_bar)

        self._apply_styles()
        self.set_status("Ready")

    # Drag support

    def _on_title_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def _on_title_move(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    # Window lifecycle

    def closeEvent(self, event):
        """Closing the window terminates the application."""
        app = QApplication.instance()
        if app is not None:
            app.quit()
        super().closeEvent(event)

    # Action handlers

    def _on_impression_clicked(self):
        if self.on_generate_impression is not None:
            self.on_generate_impression()

    def _on_record_clicked(self):
        if self.on_toggle_recording is not None:
            self.on_toggle_recording(True)

    def _on_stop_clicked(self):
        if self.on_toggle_recording is not None:
            self.on_toggle_recording(False)

    def _on_refresh_clicked(self):
        if self.on_refresh_devices is not None:
            self.on_refresh_devices()

    def _on_mic_combo_changed(self, idx: int):
        if self.on_mic_changed is None or idx < 0:
            return
        device_index = self.mic_combo.itemData(idx)  # None = system default
        self.on_mic_changed(device_index)

    def populate_microphones(self, devices: list, selected_index: Optional[int] = None):
        """
        Fill the microphone dropdown. `devices` is a list of dicts as produced by
        `hardware.recorder.list_input_devices()`. A "System default" entry is
        prepended and maps to device index=None.
        """
        self.mic_combo.blockSignals(True)
        self.mic_combo.clear()
        self.mic_combo.addItem("System default", userData=None)
        for dev in devices:
            label = dev["name"]
            if dev.get("hostapi_name"):
                label = f"{dev['name']} ({dev['hostapi_name']})"
            if dev.get("is_default"):
                label += "  [default]"
            self.mic_combo.addItem(label, userData=dev["index"])

        if selected_index is not None:
            for i in range(self.mic_combo.count()):
                if self.mic_combo.itemData(i) == selected_index:
                    self.mic_combo.setCurrentIndex(i)
                    break
        self.mic_combo.blockSignals(False)

    def set_recording_state(self, recording: bool):
        """Reflect recording state in the Record/Stop buttons and lock the mic picker."""
        self.record_btn.setEnabled(not recording)
        self.stop_btn.setEnabled(recording)
        self.mic_combo.setEnabled(not recording)
        self.refresh_btn.setEnabled(not recording)

    # Public API

    def set_status(self, text: str, color: str = "#a6e3a1"):
        """Update the status pill. Default color is green (idle/done)."""
        self.status_label.setText(f"● {text}")
        self.status_label.setStyleSheet(
            f"color: {color}; padding: 2px 10px; font-size: 11px;"
        )

    def append_text(self, text: str):
        """Append a transcribed segment to the transcript display."""
        self.editor.append(text)

    def get_findings(self) -> str:
        """Returns the current transcript text (used as LLM input)."""
        return self.editor.toPlainText()

    # Streaming partial-transcript support

    def begin_streaming(self):
        """Mark the current end-of-document as the start of a streaming partial."""
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._partial_start = cursor.position()
        self.editor.setTextCursor(cursor)

    def update_partial(self, text: str):
        """Replace the current streaming partial with the latest live transcript."""
        if self._partial_start < 0:
            return
        cursor = self.editor.textCursor()
        cursor.setPosition(self._partial_start)
        cursor.movePosition(
            QTextCursor.MoveOperation.End,
            QTextCursor.MoveMode.KeepAnchor,
        )
        cursor.removeSelectedText()
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#7f849c"))   # muted gray
        fmt.setFontItalic(True)
        cursor.insertText(text, fmt)
        self.editor.ensureCursorVisible()

    def commit_partial(self, text: str):
        """Replace the streaming partial with the final text and end streaming."""
        if self._partial_start < 0:
            # No active streaming session — just append as a new line
            if text:
                self.append_text(text)
            return
        cursor = self.editor.textCursor()
        cursor.setPosition(self._partial_start)
        cursor.movePosition(
            QTextCursor.MoveOperation.End,
            QTextCursor.MoveMode.KeepAnchor,
        )
        cursor.removeSelectedText()
        if text:
            fmt = QTextCharFormat()
            fmt.setFontItalic(False)
            fmt.setForeground(QColor("#cdd6f4"))   # same as stylesheet default
            cursor.insertText(text + "\n", fmt)
        self._partial_start = -1
        self.editor.ensureCursorVisible()

    # Styling

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
            #actionBar {
                background: #1e1e2e;
                border-top: 1px solid #45475a;
            }
            #impressionBtn {
                background: #89b4fa;
                color: #1e1e2e;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: bold;
            }
            #impressionBtn:hover { background: #b4befe; }
            #impressionBtn:disabled { background: #45475a; color: #7f849c; }
            #recordBtn {
                background: #f38ba8;
                color: #1e1e2e;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: bold;
            }
            #recordBtn:hover { background: #eba0ac; }
            #recordBtn:disabled { background: #45475a; color: #7f849c; }
            #stopBtn {
                background: #fab387;
                color: #1e1e2e;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: bold;
            }
            #stopBtn:hover { background: #f5c2a7; }
            #stopBtn:disabled { background: #45475a; color: #7f849c; }
            #clearBtn {
                background: #313244;
                color: #cdd6f4;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
            }
            #clearBtn:hover { background: #45475a; }
            #micRow { background: #1e1e2e; }
            #micLabel { color: #a6adc8; font-size: 11px; }
            #micCombo {
                background: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 3px 6px;
                font-size: 11px;
            }
            #micCombo:disabled { background: #1e1e2e; color: #7f849c; }
            #refreshBtn {
                background: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                font-size: 14px;
            }
            #refreshBtn:hover { background: #45475a; }
            #refreshBtn:disabled { background: #1e1e2e; color: #7f849c; }
            #micCombo QAbstractItemView {
                background: #181825;
                color: #cdd6f4;
                selection-background-color: #45475a;
            }
        """)
