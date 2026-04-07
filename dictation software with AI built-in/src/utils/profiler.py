import time
from loguru import logger

class LatencyTimer:
    """
    Timer utility for profiling dictation latency.
    """
    def __init__(self):
        self._starts = {}
        self._report = {}

    def start(self, name: str):
        """Starts timing a specific task."""
        self._starts[name] = time.perf_counter()

    def stop(self, name: str) -> float:
        """Stops timing and returns the elapsed time in seconds."""
        if name not in self._starts:
            return 0.0
        
        elapsed = time.perf_counter() - self._starts[name]
        self._report[name] = elapsed
        
        # Log for real-time visibility
        logger.debug(f"Task '{name}' took {elapsed:.4f}s")
        return elapsed

    def get_report(self) -> dict:
        """Returns the dictionary of all recorded latencies."""
        return self._report
