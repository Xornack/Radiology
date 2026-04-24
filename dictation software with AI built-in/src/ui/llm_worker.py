"""Qt-aware worker for long-running LLM calls.

Impression generation and Structure Report both round-trip through
Ollama synchronously (2–30s depending on cold-vs-warm + token count).
Running them on the Qt main thread freezes the entire UI. This
coordinator dispatches each call to a daemon thread and reports the
result via signals so the GUI layer can re-enable buttons and paint
the output without ever blocking.

Mirrors the shape of WarmupCoordinator — same generation-counter
pattern so that a second click cancels the first result (user likely
doesn't want stale output landing after they've moved on).
"""
import threading
from typing import Any, Callable

from PyQt6.QtCore import QObject, pyqtSignal
from loguru import logger


class LlmWorker(QObject):
    """Dispatches `generate_impression` / `structure_report` off the UI thread.

    Signals are queued to the GUI thread by Qt's AutoConnection default,
    so handlers can freely touch widgets. Results from stale runs (a
    second request arrived before the first finished) are dropped via
    the generation counter.
    """

    impression_ready = pyqtSignal(str)
    impression_failed = pyqtSignal(str)
    structure_ready = pyqtSignal(str)
    structure_failed = pyqtSignal(str)

    def __init__(self, orchestrator: Any, parent: QObject | None = None):
        super().__init__(parent)
        self.orchestrator = orchestrator
        self._lock = threading.Lock()
        self._impression_gen = 0
        self._structure_gen = 0

    def run_impression(
        self,
        findings: str,
        on_chunk: Callable[[str], None] | None = None,
    ) -> None:
        """Spawn a thread to call orchestrator.generate_impression.

        `on_chunk` receives each streamed delta on the worker thread.
        If live tokens aren't needed, omit it — the non-streaming path
        is slightly cheaper on the HTTP layer.
        """
        with self._lock:
            self._impression_gen += 1
            my_gen = self._impression_gen

        def run() -> None:
            try:
                result = self.orchestrator.generate_impression(
                    findings, on_chunk=on_chunk
                )
            except Exception as e:
                logger.error(f"Impression worker crashed: {e}")
                if self._gen_current("impression", my_gen):
                    self.impression_failed.emit(str(e))
                return
            if not self._gen_current("impression", my_gen):
                return
            if result:
                self.impression_ready.emit(result)
            else:
                # LLM client already logged the reason; UI shows a generic
                # "failed" status so user knows to retry.
                self.impression_failed.emit("empty response")

        threading.Thread(target=run, daemon=True).start()

    def run_structure(
        self,
        text: str,
        on_chunk: Callable[[str], None] | None = None,
    ) -> None:
        """Spawn a thread to call orchestrator.structure_report.

        Same contract as `run_impression`. Structure outputs are longer
        (~1024 tokens) so `on_chunk` is where live-token UX pays off
        most; the caller is free to leave it None for a simpler blocking
        flow.
        """
        with self._lock:
            self._structure_gen += 1
            my_gen = self._structure_gen

        def run() -> None:
            try:
                result = self.orchestrator.structure_report(
                    text, on_chunk=on_chunk
                )
            except Exception as e:
                logger.error(f"Structure worker crashed: {e}")
                if self._gen_current("structure", my_gen):
                    self.structure_failed.emit(str(e))
                return
            if not self._gen_current("structure", my_gen):
                return
            if result:
                self.structure_ready.emit(result)
            else:
                self.structure_failed.emit("empty response")

        threading.Thread(target=run, daemon=True).start()

    def _gen_current(self, kind: str, gen: int) -> bool:
        with self._lock:
            current = (
                self._impression_gen if kind == "impression" else self._structure_gen
            )
            return gen == current
