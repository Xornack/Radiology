from typing import Callable, Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QPushButton, QComboBox, QSizeGrip, QCheckBox,
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QColor, QTextCharFormat

from src.ai.stt_registry import dropdown_backends
from src.ui.styles import MAIN_WINDOW_QSS
from src.ui.text_streaming_controller import TextStreamingController


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
        # when the Record/Stop toggle is clicked. `on_mic_changed` fires when
        # the user picks a different microphone from the dropdown.
        self.on_generate_impression: Optional[Callable[[], None]] = None
        self.on_structure_report: Optional[Callable[[], None]] = None
        self.on_toggle_recording: Optional[Callable[[bool], None]] = None
        self.on_mic_changed: Optional[Callable[[Optional[int]], None]] = None
        self.on_refresh_devices: Optional[Callable[[], None]] = None
        self.on_mode_changed: Optional[Callable[[str], None]] = None
        # Fires with the new STT backend key when the user picks a different
        # engine from the dropdown (e.g. "whisper-local-cpu" → "sensevoice").
        self.on_stt_changed: Optional[Callable[[str], None]] = None
        # Fires with True/False when the user flips the radiology-vocabulary
        # checkbox. main.py wires this to orchestrator.radiology_mode.
        self.on_radiology_mode_changed: Optional[Callable[[bool], None]] = None

        # Tracks whether a recording session is currently active.
        self._recording: bool = False

        # True while the STT client's warm() is in flight. Record is
        # disabled and main.py's handle_trigger drops incoming triggers
        # with a feedback nudge while this is True.
        self._warming: bool = False

        # Optional profiler wired by main.py to track latency-critical
        # operations. The streaming controller reads this via a getter
        # lambda so a post-construction `window.profiler = p` just works.
        self.profiler = None

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

        # STT engine selector — pick which model transcribes the audio.
        # Whisper is fast enough for live streaming partials; Gemma runs the
        # final transcription only (slower, more capable multimodal LLM).
        stt_row = QWidget()
        stt_row.setObjectName("sttRow")
        sr_layout = QHBoxLayout(stt_row)
        sr_layout.setContentsMargins(10, 4, 10, 0)
        sr_layout.setSpacing(6)

        stt_label = QLabel("STT:")
        stt_label.setObjectName("sttLabel")
        sr_layout.addWidget(stt_label)

        self.stt_combo = QComboBox()
        self.stt_combo.setObjectName("sttCombo")
        self.stt_combo.setToolTip(
            "Speech-to-text engine. Whisper: fast, live partials. "
            "Gemma 4: multimodal LLM, final transcription only (slower)."
        )
        # Source of truth for available backends is src/ai/stt_registry.
        # Adding one there makes it appear here automatically.
        for spec in dropdown_backends():
            self.stt_combo.addItem(spec.display_name, userData=spec.key)
        self.stt_combo.currentIndexChanged.connect(self._on_stt_combo_changed)
        sr_layout.addWidget(self.stt_combo, stretch=1)

        # Radiology vocabulary toggle — applies a fuzzy-match correction pass
        # against a curated radiology term list after punctuation. Flip off
        # for non-radiology dictation so "plural" stays "plural" etc.
        self.radiology_check = QCheckBox("Radiology")
        self.radiology_check.setObjectName("radiologyCheck")
        self.radiology_check.setToolTip(
            "When on, corrects near-miss spellings to their radiology form "
            "(e.g. 'plural' → 'pleural'). Turn off for non-radiology dictation."
        )
        self.radiology_check.setChecked(True)
        self.radiology_check.toggled.connect(self._on_radiology_toggled)
        sr_layout.addWidget(self.radiology_check)

        root.addWidget(stt_row)

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

        # Partial-text state machine. The getter lambda lets main.py set
        # `window.profiler` after construction without us having to forward
        # the change to the controller.
        self._streaming_ctrl = TextStreamingController(
            self.editor,
            self._dictation_format,
            profiler_getter=lambda: self.profiler,
        )

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

        self.structure_btn = QPushButton("Structure Report")
        self.structure_btn.setObjectName("structureBtn")
        self.structure_btn.setToolTip(
            "Replace the editor contents with the ACR six-section "
            "structured template (Ctrl+Z to undo)"
        )
        self.structure_btn.clicked.connect(self._on_structure_clicked)
        ab.addWidget(self.structure_btn)

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

    def _on_structure_clicked(self):
        if self.on_structure_report is not None:
            self.on_structure_report()

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
        return data if data is not None else "inapp"

    def set_dictation_mode(self, mode: str):
        """Apply a dictation mode: locks the editor in Wedge, unlocks in In-app."""
        if self._recording:
            return
        if self.profiler:
            self.profiler.start("mode_switch")
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
        if self.profiler:
            self.profiler.stop("mode_switch")

    def _on_mode_combo_changed(self, idx: int):
        if idx < 0:
            return
        mode = self.mode_combo.itemData(idx)
        if not mode:
            return
        self.set_dictation_mode(mode)
        if self.on_mode_changed is not None:
            self.on_mode_changed(mode)

    def current_stt_backend(self) -> str:
        """Return the key of the currently-selected STT engine."""
        data = self.stt_combo.currentData()
        return data if data is not None else "whisper-local-cpu"

    def set_stt_backend(self, backend: str):
        """Sync the combo to a backend key without firing on_stt_changed."""
        for i in range(self.stt_combo.count()):
            if self.stt_combo.itemData(i) == backend:
                if self.stt_combo.currentIndex() != i:
                    self.stt_combo.blockSignals(True)
                    self.stt_combo.setCurrentIndex(i)
                    self.stt_combo.blockSignals(False)
                return

    def _on_stt_combo_changed(self, idx: int):
        if self._recording or idx < 0:
            return
        backend = self.stt_combo.itemData(idx)
        if not backend or self.on_stt_changed is None:
            return
        self.on_stt_changed(backend)

    def current_radiology_mode(self) -> bool:
        """Return the current state of the radiology-vocabulary toggle."""
        return self.radiology_check.isChecked()

    def set_radiology_mode(self, enabled: bool):
        """Sync the checkbox programmatically without firing on_radiology_mode_changed."""
        if self.radiology_check.isChecked() == enabled:
            return
        self.radiology_check.blockSignals(True)
        self.radiology_check.setChecked(enabled)
        self.radiology_check.blockSignals(False)

    def _on_radiology_toggled(self, checked: bool):
        if self.on_radiology_mode_changed is not None:
            self.on_radiology_mode_changed(checked)

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
        self.stt_combo.setEnabled(not recording)
        # Locking the vocab toggle avoids a confusing mid-session switch
        # where early partials are corrected and later ones aren't.
        self.radiology_check.setEnabled(not recording)
        # Clear/Impression would race the streaming partial: Clear drops the
        # editor contents and invalidates _committed_end; Impression reads
        # mid-dictation text and fires an LLM call that overlaps the session.
        self.clear_btn.setEnabled(not recording)
        self.impression_btn.setEnabled(not recording)
        self.structure_btn.setEnabled(not recording)
        # Editor lock: always read-only while recording (prevents collision with
        # the live partial region). When idle, read-only state follows the mode.
        self.editor.setReadOnly(recording or self.current_mode() == "wedge")

    # Public API

    def set_warming(self, on: bool) -> None:
        """Toggle the "warming up" state. When on: status → 'Warming
        model...', Record disabled. When off: status → 'Ready',
        Record enabled (recording lock permitting)."""
        self._warming = on
        if on:
            self.set_status("Warming model...", "#89b4fa")
            self.record_btn.setEnabled(False)
        else:
            self.set_status("Ready")
            # Only re-enable Record if no higher-priority lock (active
            # recording) is holding it. set_recording_state is the
            # authoritative gate during sessions.
            if not self._recording:
                self.record_btn.setEnabled(True)

    def is_warming(self) -> bool:
        return self._warming

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

    # Streaming partial-transcript support — thin delegators to the
    # TextStreamingController so callers keep the same API.

    def begin_streaming(self):
        self._streaming_ctrl.begin()

    def update_partial(self, text: str):
        self._streaming_ctrl.update_partial(text)

    def on_commit(self, text: str):
        self._streaming_ctrl.on_commit(text)

    def commit_partial(self, text: str):
        self._streaming_ctrl.commit_partial(text)

    # Styling

    def _apply_styles(self):
        self.setStyleSheet(MAIN_WINDOW_QSS)
