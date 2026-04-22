"""Two-pass profiling runners.

`run_timing_pass` invokes the scenario inside its own iteration loop —
the scenario is responsible for populating `timings_ms`. The harness
just returns the result.

`run_discovery_pass` wraps one scenario invocation in a pyinstrument
Profiler and writes the HTML trace to disk, returning the ScenarioResult
with `html_trace_relpath` set to the HTML filename (relative, because
the report lives in the same folder).
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from pyinstrument import Profiler

from tools.profiling.report import ScenarioResult


@dataclass
class ProfilingContext:
    """Bundle of arguments shared by every scenario.

    `stt_factory` returns a fresh STT client when called. Scenarios that
    need a clean (unwarmed) instance call the factory per iteration;
    scenarios that just need any client keep a single instance around.
    """

    clips_dir: Path
    iterations: int
    stt_factory: Callable[[], Any]
    output_dir: Path


Scenario = Callable[[ProfilingContext], ScenarioResult]


def run_timing_pass(scenario: Scenario, ctx: ProfilingContext) -> ScenarioResult:
    return scenario(ctx)


def run_discovery_pass(
    scenario: Scenario,
    ctx: ProfilingContext,
    html_path: Path,
) -> ScenarioResult:
    html_path.parent.mkdir(parents=True, exist_ok=True)
    profiler = Profiler()
    profiler.start()
    try:
        result = scenario(ctx)
    finally:
        profiler.stop()
    html_path.write_text(profiler.output_html(), encoding="utf-8")
    result.html_trace_relpath = html_path.name
    return result
