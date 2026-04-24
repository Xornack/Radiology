import time

import pytest

from src.core.commit_splitter import TickResult
from src.core.streaming import StreamingTranscriber


class DummyRecorder:
    def get_sample_count(self) -> int:
        return 0

    def get_wav_bytes_slice(self, start: int, end: int) -> bytes:
        return b""


class DummySTT:
    def transcribe(self, wav_bytes: bytes) -> str:
        return ""


def test_streaming_transcriber_has_commit_ready_signal(qtbot):
    st = StreamingTranscriber(DummyRecorder(), DummySTT())
    assert hasattr(st, "commit_ready")
    assert hasattr(st, "partial_ready")


def test_streaming_transcriber_get_committed_snapshot_delegates(qtbot):
    st = StreamingTranscriber(DummyRecorder(), DummySTT())
    committed, idx = st.get_committed_snapshot()
    assert committed == []
    assert idx == 0


def test_streaming_transcriber_emits_commit_and_partial(qtbot):
    st = StreamingTranscriber(DummyRecorder(), DummySTT())

    class StubSplitter:
        def __init__(self):
            self.ticks = 0

        def process_tick(self):
            self.ticks += 1
            return TickResult(commit_text="committed", partial_text="partial")

        def reset(self):
            pass

        def get_committed_snapshot(self):
            return ["committed"], 16000

    st._splitter = StubSplitter()
    st.start()

    with qtbot.waitSignal(st.commit_ready, timeout=3000) as commit_sig:
        with qtbot.waitSignal(st.partial_ready, timeout=3000) as partial_sig:
            st._tick()
            deadline = time.time() + 2.0
            while st._in_flight and time.time() < deadline:
                time.sleep(0.01)

    assert commit_sig.args == ["committed"]
    assert partial_sig.args == ["partial"]
    st.stop()


def test_streaming_transcriber_skips_signals_after_stop(qtbot):
    st = StreamingTranscriber(DummyRecorder(), DummySTT())

    class SlowSplitter:
        def process_tick(self):
            time.sleep(0.2)
            return TickResult(commit_text="c", partial_text="p")

        def reset(self):
            pass

        def get_committed_snapshot(self):
            return [], 0

    st._splitter = SlowSplitter()
    st.start()

    commit_fired = []
    partial_fired = []
    st.commit_ready.connect(lambda t: commit_fired.append(t))
    st.partial_ready.connect(lambda t: partial_fired.append(t))

    st._tick()
    st.stop()

    time.sleep(0.4)
    assert commit_fired == []
    assert partial_fired == []


def test_streaming_transcriber_stt_setter_syncs_splitter(qtbot):
    st = StreamingTranscriber(DummyRecorder(), DummySTT())
    new_stt = DummySTT()
    st.stt_client = new_stt
    assert st._splitter.stt_client is new_stt


def test_streaming_stop_waits_for_in_flight_worker(qtbot):
    """stop() must join the in-flight worker so the orchestrator's subsequent
    get_committed_snapshot() reads a consistent commit pointer."""
    st = StreamingTranscriber(DummyRecorder(), DummySTT())

    class SlowSplitter:
        def __init__(self):
            self.finished_at: float | None = None

        def process_tick(self):
            time.sleep(0.15)
            self.finished_at = time.time()
            return TickResult()

        def reset(self):
            pass

        def get_committed_snapshot(self):
            return [], 0

    slow = SlowSplitter()
    st._splitter = slow
    st.start()
    st._tick()  # dispatch a worker

    # Call stop while the worker is still in the sleep.
    stop_call_time = time.time()
    st.stop()
    stop_returned_at = time.time()

    # stop() must have blocked until the worker finished.
    assert slow.finished_at is not None
    assert stop_returned_at >= slow.finished_at
    # Sanity: it actually waited (worker sleeps 0.15s).
    assert stop_returned_at - stop_call_time >= 0.1
