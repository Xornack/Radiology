from typing import Callable, Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QPushButton, QComboBox, QSizeGrip,
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor


class MainWindow(QMainWindow):
    """
    Frameless floating dictation window.
    Stays on top of other applications and is draggable via the title bar.
    """

    DICTATION_COLOR = "#94e2d5"   # teal, distinct from the #cdd6f4 default text

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
        self.on_mode_changed: Optional[Callable[[str], None]] = None

        # Tracks whether a recording session is currently active.
        self._recording: bool = False

        # Cursor position where the current streaming partial begins.
        # -1 means no active streaming session.
        self._partial_start: int = -1
        # Tracks the live partial's length so update_partial can replace
        # [_partial_start, _partial_start + _partial_len] in place.
        self._partial_len: int = 0

        # Format applied to every dictated run (partials and commits).
        self._dictation_format = QTextCharFormat()
        self._dictation_format.setForeground(QColor(self.DICTATION_COLOR))
        self._dictation_format.setFontItalic(False)

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

        # Dictation mode row — In-app (default) or Wedge (send to focused external app)
        mode_row = QWidget()
        mode_row.setObjectName("modeRow")
        mdr = QHBoxLayout(mode_row)
        mdr.setContentsMargins(10, 4, 10, 0)
        mdr.setSpacing(6)

        mode_label = QLabel("Mode:")
        mode_label.setObjectName("modeLabel")
        mdr.addWidget(mode_label)

        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("modeCombo")
        self.mode_combo.setToolTip(
            "In-app: dictate into this editor. "
            "Wedge: dictate into whatever external window has focus."
        )
        self.mode_combo.addItem("In-app", userData="inapp")
        self.mode_combo.addItem("Wedge (any focused window)", userData="wedge")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_combo_changed)
        mdr.addWidget(self.mode_combo, stretch=1)

        root.addWidget(mode_row)

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

        # Single toggle — text/tooltip/objectName flip based on recording state.
        self.record_btn = QPushButton("● Record")
        self.record_btn.setObjectName("recordBtn")
        self.record_btn.setToolTip("Start recording (F4)")
        self.record_btn.clicked.connect(self._on_record_toggle_clicked)
        ab.addWidget(self.record_btn)

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

        # Frameless windows lack native resize handles; a QSizeGrip in the
        # bottom-right provides a visible drag target without re-enabling the frame.
        grip = QSizeGrip(root_widget)
        grip.setFixedSize(14, 14)
        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 2, 2)
        grip_row.addStretch()
        grip_row.addWidget(grip)
        root.addLayout(grip_row)

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

    def _on_record_toggle_clicked(self):
        """Single toggle: emits True if currently idle, False if currently recording."""
        if self.on_toggle_recording is not None:
            self.on_toggle_recording(not self._recording)

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

    def current_mode(self) -> str:
        """Return the active dictation mode: 'inapp' or 'wedge'."""
        data = self.mode_combo.currentData()
        return data if data else "inapp"

    def set_dictation_mode(self, mode: str):
        """Apply a dictation mode: locks the editor in Wedge, unlocks in In-app."""
        if mode == "wedge":
            self.editor.setReadOnly(True)
        else:
            self.editor.setReadOnly(False)
        # Sync combo if called programmatically
        for i in range(self.mode_combo.count()):
            if self.mode_combo.itemData(i) == mode:
                if self.mode_combo.currentIndex() != i:
                    self.mode_combo.blockSignals(True)
                    self.mode_combo.setCurrentIndex(i)
                    self.mode_combo.blockSignals(False)
                break

    def _on_mode_combo_changed(self, idx: int):
        if idx < 0:
            return
        mode = self.mode_combo.itemData(idx)
        if not mode:
            return
        self.set_dictation_mode(mode)
        if self.on_mode_changed is not None:
            self.on_mode_changed(mode)

    def set_recording_state(self, recording: bool):
        """Reflect recording state: flip the single toggle and lock mic-row widgets."""
        self._recording = recording
        if recording:
            self.record_btn.setText("■ Stop")
            self.record_btn.setToolTip("Stop recording (F4)")
            self.record_btn.setObjectName("stopBtn")
        else:
            self.record_btn.setText("● Record")
            self.record_btn.setToolTip("Start recording (F4)")
            self.record_btn.setObjectName("recordBtn")
        # Re-apply stylesheet so the objectName-based rule refreshes.
        self.record_btn.style().unpolish(self.record_btn)
        self.record_btn.style().polish(self.record_btn)

        self.mic_combo.setEnabled(not recording)
        self.refresh_btn.setEnabled(not recording)
        self.mode_combo.setEnabled(not recording)
        # Editor lock: always read-only while recording (prevents collision with
        # the live partial region). When idle, read-only state follows the mode.
        self.editor.setReadOnly(recording or self.current_mode() == "wedge")

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
        """Anchor a streaming partial region at the current cursor position.

        From this call until commit_partial, the range
        [_partial_start, _partial_start + _partial_len] is treated as the live
        partial. Everything outside that range is untouched.
        """
        cursor = self.editor.textCursor()
        self._partial_start = cursor.position()
        self._partial_len = 0

    def update_partial(self, text: str):
        """Replace the current streaming partial with the latest live transcript.

        The replacement range is [_partial_start, _partial_start + _partial_len],
        so text before and after the partial is preserved regardless of how the
        partial grows or shrinks.
        """
        if self._partial_start < 0:
            return
        cursor = self.editor.textCursor()
        cursor.setPosition(self._partial_start)
        cursor.setPosition(
            self._partial_start + self._partial_len,
            QTextCursor.MoveMode.KeepAnchor,
        )
        cursor.removeSelectedText()
        cursor.insertText(text, self._dictation_format)
        self._partial_len = len(text)
        self.editor.ensureCursorVisible()

    def commit_partial(self, text: str):
        """Replace the live partial region with the final text and end streaming.

        After insertion the editor's current char format is reset to the default
        so subsequent user typing is not inadvertently rendered in the dictation color.
        """
        if self._partial_start < 0:
            if text:
                self.append_text(text)
            return

        cursor = self.editor.textCursor()
        cursor.setPosition(self._partial_start)
        cursor.setPosition(
            self._partial_start + self._partial_len,
            QTextCursor.MoveMode.KeepAnchor,
        )
        cursor.removeSelectedText()
        if text:
            cursor.insertText(text, self._dictation_format)

        self.editor.setTextCursor(cursor)
        # Reset the editor's current char format so subsequent user typing
        # reverts to the default color instead of inheriting the dictation format.
        self.editor.setCurrentCharFormat(QTextCharFormat())

        self._partial_start = -1
        self._partial_len = 0
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
