import time

import pytest

from tools.profiling.mocks import FixedLatencySTT, MockRecorder, MockWedge


# ----- MockRecorder -----

def test_mock_recorder_returns_primed_bytes():
    audio = b"RIFF....WAVE" + b"\x00" * 100
    recorder = MockRecorder(audio_bytes=audio)
    assert recorder.get_wav_bytes() == audio


def test_mock_recorder_start_stop_are_noops():
    recorder = MockRecorder(audio_bytes=b"wav")
    recorder.start()
    recorder.stop()
    assert recorder.get_wav_bytes() == b"wav"


def test_mock_recorder_set_device_is_noop():
    recorder = MockRecorder(audio_bytes=b"wav")
    recorder.set_device(3)
    assert recorder.device is None


# ----- MockWedge -----

def test_mock_wedge_records_last_call():
    wedge = MockWedge()
    wedge.type_text("hello world")
    assert wedge.last_text == "hello world"
    assert wedge.call_count == 1


def test_mock_wedge_multiple_calls_tracked():
    wedge = MockWedge()
    wedge.type_text("first")
    wedge.type_text("second")
    assert wedge.last_text == "second"
    assert wedge.call_count == 2


# ----- FixedLatencySTT -----

def test_fixed_latency_stt_returns_canned_text():
    stt = FixedLatencySTT(latency_ms=10, text="canned")
    result = stt.transcribe(b"any-bytes")
    assert result == "canned"


def test_fixed_latency_stt_sleeps_roughly_expected_amount():
    stt = FixedLatencySTT(latency_ms=50, text="x")
    start = time.perf_counter()
    stt.transcribe(b"x")
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms >= 45, f"expected ~50 ms sleep, got {elapsed_ms:.1f} ms"
    assert elapsed_ms < 500, f"sleep should not run long, got {elapsed_ms:.1f} ms"


def test_fixed_latency_stt_supports_streaming_flag():
    stt = FixedLatencySTT()
    assert stt.supports_streaming is True


def test_fixed_latency_stt_warm_is_fast_noop_ish():
    stt = FixedLatencySTT(warm_latency_ms=5)
    start = time.perf_counter()
    stt.warm()
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 100
