from typing import Callable, Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QPushButton, QComboBox, QSizeGrip, QCheckBox,
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
        # when the Record/Stop toggle is clicked. `on_mic_changed` fires when
        # the user picks a different microphone from the dropdown.
        self.on_generate_impression: Optional[Callable[[], None]] = None
        self.on_toggle_recording: Optional[Callable[[bool], None]] = None
        self.on_mic_changed: Optional[Callable[[Optional[int]], None]] = None
        self.on_refresh_devices: Optional[Callable[[], None]] = None
        self.on_mode_changed: Optional[Callable[[str], None]] = None
        # Fires with the new STT backend key when the user picks a different
        # engine from the dropdown (e.g. "whisper-local" → "gemma-e2b").
        self.on_stt_changed: Optional[Callable[[str], None]] = None
        # Fires with True/False when the user flips the radiology-vocabulary
        # checkbox. main.py wires this to orchestrator.radiology_mode.
        self.on_radiology_mode_changed: Optional[Callable[[bool], None]] = None

        # Tracks whether a recording session is currently active.
        self._recording: bool = False

        # Bounds of the live region that spans committed + partial text.
        # `_committed_end` is the insertion anchor; up to that position,
        # text is locked in and not rewritten by update_partial. Between
        # `_committed_end` and `_partial_end` is the live partial region
        # that update_partial replaces in place. Both are -1 when no
        # streaming session is active.
        self._committed_end: int = -1
        self._partial_end: int = -1
        # Set in begin_streaming when the anchor sits after non-whitespace text:
        # successive click-on/click-off dictation sessions get a leading space
        # so the previous sentence's terminator doesn't hug the new one.
        self._needs_leading_space: bool = False
        # Set in begin_streaming: True when the dictation starts a new sentence
        # (document start, or preceding text ends with . ? !). False means the
        # session is a mid-sentence continuation and the first letter must stay
        # lowercase.
        self._capitalize_first: bool = True

        # Optional profiler wired by main.py to track latency-critical operations
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
        self.stt_combo.addItem("Whisper (local, CPU)", userData="whisper-local-cpu")
        self.stt_combo.addItem("Whisper (local, GPU)", userData="whisper-local-gpu")
        self.stt_combo.addItem("Whisper Turbo (GPU)", userData="whisper-turbo-gpu")
        # "whisper-http" backend is intentionally NOT exposed in the dropdown:
        # on a single workstation it always connection-refuses. Available via
        # STT_BACKEND=whisper-http env var for remote/containerized deployments.
        self.stt_combo.addItem("Moonshine tiny", userData="moonshine-tiny")
        self.stt_combo.addItem("Moonshine base", userData="moonshine-base")
        self.stt_combo.addItem("SenseVoice (Alibaba)", userData="sensevoice")
        # Parakeet-TDT (NeMo) is intentionally NOT exposed in the dropdown:
        # NeMo's import chain (torch-distributed / Megatron / pytorch-lightning)
        # hard-crashes on Python 3.13 Windows during ASRModel.from_pretrained,
        # with no recoverable Python exception — the whole process dies. Still
        # reachable via STT_BACKEND=parakeet-tdt if someone wants to debug.
        self.stt_combo.addItem("Vosk (offline)", userData="vosk")
        self.stt_combo.addItem("Gemma 4 E2B-it", userData="gemma-e2b")
        self.stt_combo.addItem("Gemma 4 E2B-it (4-bit)", userData="gemma-e2b-4bit")
        self.stt_combo.addItem("Gemma 4 E4B-it", userData="gemma-e4b")
        self.stt_combo.addItem("Gemma 4 E4B-it (4-bit)", userData="gemma-e4b-4bit")
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

    def _apply_first_letter_case(self, text: str) -> str:
        """Uppercase or lowercase the first letter per the session's cap-first flag.

        Normalizes text from either source (orchestrator output, which may be
        uncapitalized in-app, or streaming partials, which cap by default) so
        the first letter matches editor context.
        """
        if self._capitalize_first:
            return text[0].upper() + text[1:]
        return text[0].lower() + text[1:]

    def begin_streaming(self):
        """Anchor a streaming session at the current cursor position.

        If there is an active selection, the selected text is removed first so
        dictation replaces it (standard "type over selection" behavior). Until
        commit_partial, the range [_committed_end, _partial_end] is the live
        partial region that update_partial replaces in place. Below
        _committed_end is locked-in text (initially empty; grows as on_commit
        fires during the session).
        """
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()
            self.editor.setTextCursor(cursor)
        pos = cursor.position()
        self._committed_end = pos
        self._partial_end = pos
        doc_text = self.editor.toPlainText()
        self._needs_leading_space = (
            pos > 0
            and not doc_text[pos - 1].isspace()
        )
        stripped_prefix = doc_text[:pos].rstrip()
        self._capitalize_first = (
            not stripped_prefix
            or stripped_prefix[-1] in ".?!"
        )

    def update_partial(self, text: str):
        """Replace [_committed_end, _partial_end] with `text`."""
        if self._committed_end < 0:
            return
        if self.profiler:
            self.profiler.start("partial_replace")
        if text:
            text = self._apply_first_letter_case(text)
            if self._needs_leading_space:
                text = " " + text
        cursor = self.editor.textCursor()
        cursor.setPosition(self._committed_end)
        cursor.setPosition(self._partial_end, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text, self._dictation_format)
        self._partial_end = self._committed_end + len(text)
        self.editor.ensureCursorVisible()
        if self.profiler:
            self.profiler.stop("partial_replace")

    def on_commit(self, text: str):
        """Lock the current partial region as committed.

        Replaces [_committed_end, _partial_end] with `text` (the commit
        transcription, which can differ from the last displayed partial since
        the STT has more audio context), then advances _committed_end so
        subsequent update_partial calls don't overwrite the locked text.

        After the first commit, subsequent updates are mid-dictation-session:
        no leading space is needed, and the session-start capitalization has
        already been applied to the text that preceded this commit.
        """
        if self._committed_end < 0:
            return
        if text:
            text = self._apply_first_letter_case(text)
            if self._needs_leading_space:
                text = " " + text
        cursor = self.editor.textCursor()
        cursor.setPosition(self._committed_end)
        cursor.setPosition(self._partial_end, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text, self._dictation_format)
        new_end = self._committed_end + len(text)
        self._committed_end = new_end
        self._partial_end = new_end
        # Subsequent partials/commits are mid-session continuations.
        self._needs_leading_space = False
        self._capitalize_first = False
        self.editor.ensureCursorVisible()

    def commit_partial(self, text: str):
        """Replace the live partial region with the final text and end streaming.

        After insertion the editor's current char format is reset to the default
        so subsequent user typing is not inadvertently rendered in the dictation color.
        """
        if self._committed_end < 0:
            if text:
                self.append_text(text)
            return

        if text:
            text = self._apply_first_letter_case(text)
            if self._needs_leading_space:
                text = " " + text

        cursor = self.editor.textCursor()
        cursor.setPosition(self._committed_end)
        cursor.setPosition(self._partial_end, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        if text:
            cursor.insertText(text, self._dictation_format)

        self.editor.setTextCursor(cursor)
        self.editor.setCurrentCharFormat(QTextCharFormat())

        self._committed_end = -1
        self._partial_end = -1
        self._needs_leading_space = False
        self._capitalize_first = True
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
            #modeRow { background: #1e1e2e; }
            #modeLabel { color: #a6adc8; font-size: 11px; }
            #modeCombo {
                background: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 3px 6px;
                font-size: 11px;
            }
            #modeCombo:disabled { background: #1e1e2e; color: #7f849c; }
            #modeCombo QAbstractItemView {
                background: #181825;
                color: #cdd6f4;
                selection-background-color: #45475a;
            }
            #sttRow { background: #1e1e2e; }
            #sttLabel { color: #a6adc8; font-size: 11px; }
            #sttCombo {
                background: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 3px 6px;
                font-size: 11px;
            }
            #sttCombo:disabled { background: #1e1e2e; color: #7f849c; }
            #sttCombo QAbstractItemView {
                background: #181825;
                color: #cdd6f4;
                selection-background-color: #45475a;
            }
        """)
