import threading
from typing import Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from loguru import logger

from src.core.commit_splitter import CommitSplitter


class StreamingTranscriber(QObject):
    """Qt wrapper around CommitSplitter.

    Schedules ticks on a QTimer and dispatches each tick to a worker
    thread so Qt's event loop stays responsive. Emits `commit_ready`
    once per commit point and `partial_ready` per live-partial update.
    Both signals are queued to the GUI thread automatically by Qt's
    AutoConnection default.
    """
    partial_ready = pyqtSignal(str)
    commit_ready = pyqtSignal(str)

    def __init__(
        self,
        recorder,
        stt_client,
        interval_ms: int = 1500,
        sample_rate: int = 16000,
        parent=None,
    ):
        super().__init__(parent)
        self.recorder = recorder
        self._stt_client = stt_client
        self.interval_ms = interval_ms
        self.sample_rate = sample_rate
        self._splitter = CommitSplitter(
            recorder=recorder,
            stt_client=stt_client,
            sample_rate=sample_rate,
        )
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._worker: Optional[threading.Thread] = None
        self._in_flight = False
        self._active = False

    def start(self):
        self._splitter.reset()
        self._active = True
        self._in_flight = False
        self._timer.start(self.interval_ms)

    def stop(self):
        """Stops scheduling new ticks. In-flight workers finish on their
        own but their results are discarded because `_active` is False."""
        self._active = False
        self._timer.stop()

    def get_committed_snapshot(self) -> tuple[list[str], int]:
        """Orchestrator uses this on Stop. Safe to call after `stop()`."""
        return self._splitter.get_committed_snapshot()

    @property
    def stt_client(self):
        return self._stt_client

    @stt_client.setter
    def stt_client(self, value):
        """Setter so main.py can swap STT backends at runtime. Keeps the
        splitter's client reference in sync."""
        self._stt_client = value
        if hasattr(self, "_splitter") and self._splitter is not None:
            self._splitter.stt_client = value

    def _tick(self):
        if self._in_flight or not self._active:
            return
        self._in_flight = True
        self._worker = threading.Thread(target=self._run_tick, daemon=True)
        self._worker.start()

    def _run_tick(self):
        try:
            result = self._splitter.process_tick()
            if not self._active:
                return
            if result.commit_text:
                self.commit_ready.emit(result.commit_text)
            if result.partial_text:
                self.partial_ready.emit(result.partial_text)
        except Exception as e:
            logger.error(f"Streaming tick failed: {e}")
        finally:
            self._in_flight = False
