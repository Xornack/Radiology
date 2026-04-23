"""Qt-aware wrapper around STT client warm() calls.

Runs the blocking warm in a daemon thread and reports completion via
Qt signals so the GUI thread can update the status bar and enable the
Record button. Uses a monotonic generation counter so that swapping
STT backends mid-warm discards the stale signal from the superseded
client instead of confusing the UI.
"""
import threading
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal
from loguru import logger


class WarmupCoordinator(QObject):
    """Owns the warm lifecycle. Consumers connect to `ready` / `failed`
    and call `warm_in_background(stt_client)` whenever a new client
    needs loading (startup, backend swap)."""

    ready = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._generation = 0
        self._lock = threading.Lock()

    def warm_in_background(self, stt_client: Any) -> None:
        with self._lock:
            self._generation += 1
            my_gen = self._generation

        if not hasattr(stt_client, "warm"):
            # HTTP-style clients load on demand and have no warm().
            # Treat as ready-immediately so the UI doesn't get stuck.
            self.ready.emit()
            return

        def run() -> None:
            try:
                stt_client.warm()
            except Exception as e:
                logger.error(f"STT warm failed: {e}")
                if self._generation_current(my_gen):
                    self.failed.emit(str(e))
                return
            if self._generation_current(my_gen):
                self.ready.emit()

        threading.Thread(target=run, daemon=True).start()

    def _generation_current(self, gen: int) -> bool:
        with self._lock:
            return gen == self._generation
