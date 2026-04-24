import time
from contextlib import contextmanager
from loguru import logger


class LatencyTimer:
    """
    Timer utility for profiling dictation latency.
    """
    def __init__(self):
        self._starts: dict[str, float] = {}
        self._report: dict[str, float] = {}

    def start(self, name: str):
        """Starts timing a specific task."""
        self._starts[name] = time.perf_counter()

    def stop(self, name: str) -> float:
        """Stops timing and returns the elapsed time in seconds."""
        if name not in self._starts:
            return 0.0

        elapsed = time.perf_counter() - self._starts[name]
        self._report[name] = elapsed

        logger.debug(f"Task '{name}' took {elapsed:.4f}s")
        return elapsed

    @contextmanager
    def timed(self, name: str):
        """Context-manager form: `with profiler.timed("foo"): ...`.

        Reduces three-line start/try/finally blocks to a single line at
        call sites. Returns the elapsed time via `.get_report()[name]`
        the same way `stop()` does.
        """
        self.start(name)
        try:
            yield
        finally:
            self.stop(name)

    def get_report(self) -> dict[str, float]:
        """Returns the dictionary of all recorded latencies."""
        return self._report


@contextmanager
def _optional_timer(profiler, name: str):
    """Null-safe wrapper: if `profiler` is None, yields without timing.

    Used by hot-path code (commit_splitter, text pipeline) where the
    profiler is wired in from main.py but omitted in tests.
    """
    if profiler is None:
        yield
        return
    with profiler.timed(name):
        yield
