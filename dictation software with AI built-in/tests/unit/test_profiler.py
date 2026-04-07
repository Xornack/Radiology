import pytest
import time
from src.utils.profiler import LatencyTimer

def test_latency_timer_records_time():
    """
    Ensures that LatencyTimer correctly measures a sleep interval.
    """
    timer = LatencyTimer()
    timer.start("test_task")
    time.sleep(0.05) # 50ms
    elapsed = timer.stop("test_task")
    
    # Check that elapsed time is approximately 50ms
    assert 0.04 <= elapsed <= 0.1

def test_latency_timer_logs_multiple_steps():
    """
    Ensures we can track multiple named steps in a pipeline.
    """
    timer = LatencyTimer()
    timer.start("step1")
    timer.stop("step1")
    timer.start("step2")
    timer.stop("step2")
    
    report = timer.get_report()
    assert "step1" in report
    assert "step2" in report
