import wave
from pathlib import Path

import pytest

from tools.profiling.harness import ProfilingContext
from tools.profiling.mocks import FixedLatencySTT
from tools.profiling.scenarios import (
    scenario_cold_import,
    scenario_streaming_tick,
    scenario_text_post_processing,
)


def _write_silence_wav(path: Path, duration_s: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = int(16000 * duration_s)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * n)


def _ctx(tmp_path: Path, iterations: int = 3) -> ProfilingContext:
    for name, dur in (("short.wav", 1.0), ("medium.wav", 2.0), ("long.wav", 3.0)):
        _write_silence_wav(tmp_path / name, dur)
    return ProfilingContext(
        clips_dir=tmp_path,
        iterations=iterations,
        stt_factory=lambda: FixedLatencySTT(latency_ms=5, warm_latency_ms=5),
        output_dir=tmp_path,
    )


def test_text_post_processing_returns_result(tmp_path: Path):
    result = scenario_text_post_processing(_ctx(tmp_path, iterations=10))
    assert result.name == "text_post_processing"
    assert result.timings_ms
    for samples in result.timings_ms.values():
        assert len(samples) == 10


def test_text_post_processing_measures_separate_spans(tmp_path: Path):
    result = scenario_text_post_processing(_ctx(tmp_path, iterations=3))
    assert "scrub" in result.timings_ms
    assert "punctuation" in result.timings_ms
    assert "lexicon" in result.timings_ms


def test_cold_import_returns_result(tmp_path: Path):
    result = scenario_cold_import(_ctx(tmp_path, iterations=1))
    assert result.name == "cold_import"
    assert "wall" in result.timings_ms
    assert len(result.timings_ms["wall"]) == 1
    assert result.timings_ms["wall"][0] > 10


def test_streaming_tick_runs_three_buffer_sizes(tmp_path: Path):
    result = scenario_streaming_tick(_ctx(tmp_path, iterations=2))
    assert result.name == "streaming_tick"
    assert "5s" in result.timings_ms
    assert "15s" in result.timings_ms
    assert "30s" in result.timings_ms
    for samples in result.timings_ms.values():
        assert len(samples) == 2


# ----- sensevoice_warm -----

def test_sensevoice_warm_returns_result(tmp_path: Path):
    from tools.profiling.scenarios import scenario_sensevoice_warm
    result = scenario_sensevoice_warm(_ctx(tmp_path, iterations=2))
    assert result.name == "sensevoice_warm"
    assert "warm" in result.timings_ms
    assert len(result.timings_ms["warm"]) == 2


def test_sensevoice_warm_builds_fresh_client_each_iteration(tmp_path: Path):
    from tools.profiling.scenarios import scenario_sensevoice_warm

    builds = {"n": 0}

    def factory():
        builds["n"] += 1
        return FixedLatencySTT(latency_ms=1, warm_latency_ms=5)

    ctx = _ctx(tmp_path, iterations=3)
    ctx = ProfilingContext(
        clips_dir=ctx.clips_dir,
        iterations=ctx.iterations,
        stt_factory=factory,
        output_dir=ctx.output_dir,
    )
    scenario_sensevoice_warm(ctx)
    assert builds["n"] == 3


# ----- stt_hot_path -----

def test_stt_hot_path_runs_three_clip_lengths(tmp_path: Path):
    from tools.profiling.scenarios import scenario_stt_hot_path
    result = scenario_stt_hot_path(_ctx(tmp_path, iterations=2))
    assert result.name == "stt_hot_path"
    assert "short" in result.timings_ms
    assert "medium" in result.timings_ms
    assert "long" in result.timings_ms
    for samples in result.timings_ms.values():
        assert len(samples) == 2


# ----- full_pipeline -----

def test_full_pipeline_runs_each_clip_length(tmp_path: Path):
    from tools.profiling.scenarios import scenario_full_pipeline
    result = scenario_full_pipeline(_ctx(tmp_path, iterations=2))
    assert result.name == "full_pipeline"
    assert "short" in result.timings_ms
    assert "medium" in result.timings_ms
    assert "long" in result.timings_ms
    for samples in result.timings_ms.values():
        assert len(samples) == 2


def test_full_pipeline_inapp_mode_smoke(tmp_path: Path):
    from tools.profiling.scenarios import scenario_full_pipeline
    result = scenario_full_pipeline(_ctx(tmp_path, iterations=1))
    assert result.name == "full_pipeline"
