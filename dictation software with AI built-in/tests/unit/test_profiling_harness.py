import time
from pathlib import Path

import pytest

from tools.profiling.harness import (
    ProfilingContext,
    run_discovery_pass,
    run_timing_pass,
)
from tools.profiling.mocks import FixedLatencySTT
from tools.profiling.report import ScenarioResult


def _trivial_scenario(ctx) -> ScenarioResult:
    timings: dict[str, list[float]] = {"work": []}
    for _ in range(ctx.iterations):
        start = time.perf_counter()
        time.sleep(0.002)
        timings["work"].append((time.perf_counter() - start) * 1000)
    return ScenarioResult(
        name="trivial",
        params={"n": ctx.iterations},
        timings_ms=timings,
    )


def _make_ctx(tmp_path: Path, iterations: int = 3) -> ProfilingContext:
    return ProfilingContext(
        clips_dir=tmp_path,
        iterations=iterations,
        stt_factory=lambda: FixedLatencySTT(latency_ms=1, warm_latency_ms=1),
        output_dir=tmp_path,
    )


def test_run_timing_pass_returns_scenario_result(tmp_path: Path):
    result = run_timing_pass(_trivial_scenario, _make_ctx(tmp_path, iterations=3))
    assert isinstance(result, ScenarioResult)
    assert result.name == "trivial"


def test_run_timing_pass_populates_iterations(tmp_path: Path):
    result = run_timing_pass(_trivial_scenario, _make_ctx(tmp_path, iterations=5))
    assert len(result.timings_ms["work"]) == 5


def test_run_discovery_pass_writes_non_empty_html(tmp_path: Path):
    html_path = tmp_path / "trace.html"
    run_discovery_pass(
        _trivial_scenario,
        _make_ctx(tmp_path, iterations=1),
        html_path=html_path,
    )
    assert html_path.exists()
    assert html_path.stat().st_size > 100
    assert "<html" in html_path.read_text(encoding="utf-8").lower()


def test_run_discovery_pass_returns_result_with_relpath(tmp_path: Path):
    html_path = tmp_path / "sub" / "trace.html"
    result = run_discovery_pass(
        _trivial_scenario,
        _make_ctx(tmp_path, iterations=1),
        html_path=html_path,
    )
    assert isinstance(result, ScenarioResult)
    assert result.html_trace_relpath is not None
    assert result.html_trace_relpath.endswith("trace.html")
