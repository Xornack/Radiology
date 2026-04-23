import time

import pytest

from src.ui.warmup_coordinator import WarmupCoordinator


class _FastSttWithWarm:
    def __init__(self):
        self.warmed = False

    def warm(self) -> None:
        time.sleep(0.05)
        self.warmed = True


class _SlowSttWithWarm:
    def __init__(self, delay_s: float = 0.3):
        self._delay = delay_s
        self.warmed = False

    def warm(self) -> None:
        time.sleep(self._delay)
        self.warmed = True


class _FailingSttWithWarm:
    def warm(self) -> None:
        raise RuntimeError("model load exploded")


class _SttWithoutWarm:
    """HTTP-style client — no warm method."""


def test_warm_in_background_emits_ready_on_success(qtbot):
    coord = WarmupCoordinator()
    with qtbot.waitSignal(coord.ready, timeout=3000):
        coord.warm_in_background(_FastSttWithWarm())


def test_warm_in_background_emits_failed_with_message_on_exception(qtbot):
    coord = WarmupCoordinator()
    with qtbot.waitSignal(coord.failed, timeout=3000) as sig:
        coord.warm_in_background(_FailingSttWithWarm())
    assert len(sig.args) == 1
    assert "model load exploded" in sig.args[0]


def test_warm_in_background_with_no_warm_attr_emits_ready_immediately(qtbot):
    coord = WarmupCoordinator()
    with qtbot.waitSignal(coord.ready, timeout=500):
        coord.warm_in_background(_SttWithoutWarm())


def test_warm_in_background_second_call_supersedes_first(qtbot):
    coord = WarmupCoordinator()

    ready_calls = []
    coord.ready.connect(lambda: ready_calls.append(time.perf_counter()))

    slow = _SlowSttWithWarm(delay_s=0.3)
    fast = _FastSttWithWarm()

    coord.warm_in_background(slow)
    coord.warm_in_background(fast)

    qtbot.waitUntil(lambda: len(ready_calls) >= 1, timeout=1000)

    time.sleep(0.6)
    assert len(ready_calls) == 1, f"expected exactly 1 ready, got {len(ready_calls)}"


def test_warm_in_background_success_does_not_emit_failed(qtbot):
    coord = WarmupCoordinator()
    failed_calls = []
    coord.failed.connect(lambda msg: failed_calls.append(msg))
    with qtbot.waitSignal(coord.ready, timeout=2000):
        coord.warm_in_background(_FastSttWithWarm())
    time.sleep(0.2)
    assert failed_calls == []
