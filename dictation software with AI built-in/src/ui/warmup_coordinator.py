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
        # Tracked so shutdown() can join them with a timeout. Daemon
        # threads die silently with no log when the process exits; on
        # a clean Quit we'd rather wait briefly and know if a warm
        # was stranded mid-load (model-load bug surfaces in the log).
        self._threads: list[threading.Thread] = []

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

        t = threading.Thread(target=run, daemon=True)
        with self._lock:
            self._threads.append(t)
        t.start()

    def shutdown(self, timeout: float = 3.0) -> None:
        """Best-effort join of in-flight warmups. Logs a warning if a
        thread is still alive after `timeout`.

        Called from the app's aboutToQuit handler so model-load hangs
        don't become invisible daemon-thread exits during shutdown."""
        with self._lock:
            pending = [t for t in self._threads if t.is_alive()]
        for t in pending:
            t.join(timeout=timeout)
            if t.is_alive():
                logger.warning(
                    "WarmupCoordinator: thread still running at shutdown — "
                    "model load may be hung"
                )

    def _generation_current(self, gen: int) -> bool:
        with self._lock:
            return gen == self._generation
