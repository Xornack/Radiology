"""Qt-aware worker for the post-Stop dictation pipeline.

Moves `orchestrator.handle_trigger_up()` off the Qt main thread so the
UI stays responsive while the Stop-path remainder is being transcribed
(1-5s depending on audio length and STT engine). The worker emits a
single signal with (mode, result_text) on success or (mode, error_msg)
on failure; the GUI handler marshals the status-bar update.

Why a worker instead of a naked threading.Thread: we need Qt-signal
marshaling onto the main thread, and we want one shared generation
counter so a second Stop press (shouldn't happen, but defensive) drops
the stale result. Mirrors LlmWorker's shape.
"""
import threading
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal
from loguru import logger


class StopPathWorker(QObject):
    """Runs orchestrator.handle_trigger_up on a daemon thread.

    Signals queue to the GUI thread (Qt AutoConnection default).
    Handlers can touch widgets, timers, and the editor without any
    further marshaling.
    """

    # (mode, result_text) — result_text may be "" if the remainder was silent
    finished = pyqtSignal(str, str)
    # (mode, error_msg) — raised exceptions land here
    failed = pyqtSignal(str, str)

    def __init__(self, orchestrator: Any, parent: QObject | None = None):
        super().__init__(parent)
        self.orchestrator = orchestrator
        self._lock = threading.Lock()
        self._generation = 0

    def run(self, mode: str) -> None:
        """Spawn a daemon thread running `handle_trigger_up(mode=mode)`.

        Caller should disable the Record button (or set a busy status)
        before calling and rely on the `finished` / `failed` signal to
        re-enable. Re-entrancy isn't expected at the UI layer, but the
        generation counter guards against stale signals just in case.
        """
        with self._lock:
            self._generation += 1
            my_gen = self._generation

        def target() -> None:
            try:
                result = self.orchestrator.handle_trigger_up(mode=mode)
            except Exception as e:
                logger.error(f"Stop-path worker crashed: {e}")
                if self._gen_current(my_gen):
                    self.failed.emit(mode, str(e))
                return
            if self._gen_current(my_gen):
                self.finished.emit(mode, result or "")

        threading.Thread(target=target, daemon=True).start()

    def _gen_current(self, gen: int) -> bool:
        with self._lock:
            return gen == self._generation
