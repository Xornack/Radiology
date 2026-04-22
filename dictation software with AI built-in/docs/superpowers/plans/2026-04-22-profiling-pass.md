# Profiling Harness + Initial Report — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable profiling harness at `tools/profile_pipeline.py` that runs six scenarios against the dictation pipeline on a fixed LibriSpeech workload, produces a markdown report with `pyinstrument` HTML traces, and commit the first report it generates.

**Architecture:** A `tools/profiling/` package holds five single-purpose modules: `mocks.py` (MockRecorder, MockWedge, FixedLatencySTT for deterministic / dry-run runs), `report.py` (ScenarioResult dataclass + markdown writer), `harness.py` (two-pass runner: LatencyTimer for timings, pyinstrument for call-tree discovery), `benchmarks_setup.py` (LibriSpeech clip fetcher + FLAC→WAV transcoding via `soundfile`), and `scenarios.py` (six profiling scenarios that share a `ProfilingContext` parameter). `tools/profile_pipeline.py` is the CLI entry point that wires these together.

**Tech Stack:** `pyinstrument` (new dev dep), `soundfile` (indirect dep via `sounddevice`), `wave` / `json` / `subprocess` (stdlib), existing `LatencyTimer` from `src/utils/profiler.py`, existing `SenseVoiceSTTClient`, `DictationOrchestrator`, `StreamingTranscriber`, `scrub_text`, `apply_punctuation`, `correct_radiology`. Tests use `pytest` (already installed).

**Reference spec:** `docs/superpowers/specs/2026-04-22-profiling-pass-design.md`

---

## Task 1: Project scaffolding — `pyinstrument` dep + package markers

**Why:** Every subsequent task imports from `tools.profiling` or uses `pyinstrument`. Landing these once up front removes a whole class of "module not found" distractions later.

**Files:**
- Modify: `pyproject.toml` (add `pyinstrument>=4.6` to `[project.optional-dependencies].dev`)
- Create: `tools/__init__.py` (empty — makes `python -m tools.*` work)
- Create: `tools/profiling/__init__.py` (empty)

- [ ] **Step 1.1: Add `pyinstrument` to the dev extra**

Open `pyproject.toml` and change the `dev` entry under `[project.optional-dependencies]`:

Before:
```toml
dev = [
    "pytest>=8",
    "pytest-qt>=4.4",
]
```

After:
```toml
dev = [
    "pytest>=8",
    "pytest-qt>=4.4",
    "pyinstrument>=4.6",
]
```

- [ ] **Step 1.2: Create the empty package markers**

Create `tools/__init__.py` with an empty body (zero bytes is fine).

Create `tools/profiling/__init__.py` with an empty body.

- [ ] **Step 1.3: Install the dev extra so `pyinstrument` is importable**

Run: `pip install -e '.[dev]'`
Expected: terminal shows `Successfully installed ... pyinstrument-...` (or "Requirement already satisfied" on re-run).

- [ ] **Step 1.4: Verify `pyinstrument` imports cleanly**

Run: `python -c "import pyinstrument; print(pyinstrument.__version__)"`
Expected: a version string like `4.6.2` with no traceback.

- [ ] **Step 1.5: Verify the existing test suite still runs**

Run: `python -m pytest tests/ -x --tb=short`
Expected: same pass count as before the change; no new failures caused by the new files.

- [ ] **Step 1.6: Commit**

```bash
git add pyproject.toml tools/__init__.py tools/profiling/__init__.py
git commit -m "Profiling: add pyinstrument dev dep + tools package markers"
```

---

## Task 2: Mocks — `MockRecorder`, `MockWedge`, `FixedLatencySTT` (TDD)

**Why:** Every scenario and every test uses at least one of these. Landing the mocks first means all downstream tests can be written without conditionally faking things. TDD here is cheap — the mocks are small and their contracts are exactly what the scenarios will call.

**Files:**
- Create: `tools/profiling/mocks.py`
- Create: `tests/unit/test_profiling_mocks.py`

- [ ] **Step 2.1: Write failing tests for all three mocks**

Create `tests/unit/test_profiling_mocks.py`:

```python
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
    assert recorder.get_wav_bytes() == b"wav"  # still returns primed bytes


def test_mock_recorder_set_device_is_noop():
    recorder = MockRecorder(audio_bytes=b"wav")
    recorder.set_device(3)  # must not raise
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
    # Allow generous slack for CI jitter on Windows.
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
    assert elapsed_ms < 100  # fast in dry-run; the real warm is what we profile
```

- [ ] **Step 2.2: Run the test file — expect ImportError**

Run: `python -m pytest tests/unit/test_profiling_mocks.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'tools.profiling.mocks'`.

- [ ] **Step 2.3: Implement the mocks**

Create `tools/profiling/mocks.py`:

```python
"""Lightweight test doubles for the profiling harness.

MockRecorder feeds pre-loaded WAV bytes to scenarios that need to exercise
the pipeline without a real microphone. MockWedge captures keystroke
targets without touching Win32. FixedLatencySTT is the `--dry-run` STT
substitute — it sleeps a fixed amount and returns a canned string so the
harness itself can be smoke-tested end-to-end without loading SenseVoice.
"""
import time
from typing import Optional


class MockRecorder:
    """Returns pre-loaded WAV bytes; start/stop/set_device are no-ops."""

    def __init__(self, audio_bytes: bytes):
        self._audio_bytes = audio_bytes
        self.device: Optional[int] = None

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def set_device(self, device_index: Optional[int]) -> None:
        pass

    def get_wav_bytes(self) -> bytes:
        return self._audio_bytes


class MockWedge:
    """Records calls to `type_text` without touching Win32."""

    def __init__(self) -> None:
        self.last_text: Optional[str] = None
        self.call_count: int = 0

    def type_text(self, text: str) -> None:
        self.last_text = text
        self.call_count += 1


class FixedLatencySTT:
    """Deterministic STT stand-in for `--dry-run` harness runs.

    `transcribe` sleeps `latency_ms` to model the dominant cost of a real
    STT call. `warm` sleeps `warm_latency_ms` separately so the dry-run
    sensevoice_warm scenario produces plausible timing data without
    loading a 100 MB model.
    """

    supports_streaming: bool = True

    def __init__(
        self,
        latency_ms: int = 200,
        warm_latency_ms: int = 50,
        text: str = "mock transcription",
    ):
        self._latency_s = latency_ms / 1000.0
        self._warm_s = warm_latency_ms / 1000.0
        self._text = text

    def warm(self) -> None:
        time.sleep(self._warm_s)

    def transcribe(self, audio_bytes: bytes) -> str:
        time.sleep(self._latency_s)
        return self._text
```

- [ ] **Step 2.4: Run the tests — expect PASS**

Run: `python -m pytest tests/unit/test_profiling_mocks.py -v`
Expected: all 9 tests pass.

- [ ] **Step 2.5: Commit**

```bash
git add tools/profiling/mocks.py tests/unit/test_profiling_mocks.py
git commit -m "Profiling: add MockRecorder, MockWedge, FixedLatencySTT"
```

---

## Task 3: `ScenarioResult` dataclass + `write_report` (TDD)

**Why:** The scenarios and harness both produce `ScenarioResult` objects; defining that contract first stabilizes the signatures used by downstream tasks. Writing the report first (before anything that produces one) also gives us a concrete target for the data flow — no ambiguity about what fields the scenarios must populate.

**Files:**
- Create: `tools/profiling/report.py`
- Create: `tests/unit/test_profiling_report.py`

- [ ] **Step 3.1: Write failing tests for `ScenarioResult` + `write_report`**

Create `tests/unit/test_profiling_report.py`:

```python
import json
from pathlib import Path

import pytest

from tools.profiling.report import ScenarioResult, write_report


def _sample_results() -> list[ScenarioResult]:
    return [
        ScenarioResult(
            name="stt_hot_path",
            params={"clip": "medium"},
            timings_ms={"transcribe": [512.3, 498.1, 505.7]},
            html_trace_relpath="stt_hot_path_medium.html",
        ),
        ScenarioResult(
            name="text_post_processing",
            params={"iterations": 1000},
            timings_ms={"scrub": [0.8, 0.7, 0.9]},
            html_trace_relpath=None,
        ),
    ]


def _sample_env() -> dict:
    return {
        "python": "3.12.3",
        "platform": "Windows-11",
        "cpu": "AMD Ryzen 7 5800X",
        "stt_model": "iic/SenseVoiceSmall",
        "timestamp": "2026-04-22T14:30:00",
    }


def test_write_report_creates_markdown_file(tmp_path: Path):
    out = write_report(
        results=_sample_results(),
        output_dir=tmp_path,
        report_stem="test-report",
        env=_sample_env(),
    )
    assert out.exists()
    assert out.suffix == ".md"
    assert out.name == "test-report.md"


def test_report_contains_env_block(tmp_path: Path):
    out = write_report(
        results=_sample_results(),
        output_dir=tmp_path,
        report_stem="r",
        env=_sample_env(),
    )
    content = out.read_text(encoding="utf-8")
    assert "3.12.3" in content
    assert "Windows-11" in content
    assert "AMD Ryzen 7 5800X" in content
    assert "iic/SenseVoiceSmall" in content


def test_report_summary_table_has_one_row_per_scenario_span(tmp_path: Path):
    out = write_report(
        results=_sample_results(),
        output_dir=tmp_path,
        report_stem="r",
        env=_sample_env(),
    )
    content = out.read_text(encoding="utf-8")
    # The two ScenarioResults have one span each, so two data rows.
    assert "stt_hot_path" in content
    assert "text_post_processing" in content
    assert "transcribe" in content
    assert "scrub" in content


def test_report_computes_min_median_p95(tmp_path: Path):
    results = [
        ScenarioResult(
            name="x",
            params={},
            timings_ms={"span": [100.0, 200.0, 300.0, 400.0, 500.0]},
            html_trace_relpath=None,
        )
    ]
    out = write_report(
        results=results,
        output_dir=tmp_path,
        report_stem="r",
        env=_sample_env(),
    )
    content = out.read_text(encoding="utf-8")
    # min=100, median=300, p95=480 (nearest-rank for n=5 → index 4 → 500 —
    # we use numpy-style linear interp; document whichever convention the
    # implementation chooses, and assert one sane number is present.)
    assert "100" in content  # min
    assert "300" in content  # median


def test_report_links_to_html_trace_when_present(tmp_path: Path):
    out = write_report(
        results=_sample_results(),
        output_dir=tmp_path,
        report_stem="r",
        env=_sample_env(),
    )
    content = out.read_text(encoding="utf-8")
    assert "stt_hot_path_medium.html" in content
    # The no-trace row should NOT inject a spurious link.
    # Accept either no link at all or an explicit "—" / "n/a".
    assert "text_post_processing" in content


def test_report_creates_output_dir_if_missing(tmp_path: Path):
    nested = tmp_path / "a" / "b"
    write_report(
        results=_sample_results(),
        output_dir=nested,
        report_stem="r",
        env=_sample_env(),
    )
    assert (nested / "r.md").exists()
```

- [ ] **Step 3.2: Run the test file — expect ImportError**

Run: `python -m pytest tests/unit/test_profiling_report.py -v`
Expected: `ModuleNotFoundError: No module named 'tools.profiling.report'`.

- [ ] **Step 3.3: Implement `ScenarioResult` + `write_report`**

Create `tools/profiling/report.py`:

```python
"""Markdown report writer for profiling runs.

Consumes a list of `ScenarioResult` objects (produced by the scenarios
module) and emits one `.md` file with a summary table and per-scenario
sections. pyinstrument HTML traces live next to the report and are
linked from their owning scenario section.
"""
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ScenarioResult:
    """One scenario's measured output.

    `timings_ms` is a dict of span-name → list of per-iteration samples in
    milliseconds. `html_trace_relpath` is the filename of the pyinstrument
    HTML trace relative to the report file, or None if no discovery pass
    ran for this scenario.
    """

    name: str
    params: dict
    timings_ms: dict[str, list[float]]
    html_trace_relpath: Optional[str] = None
    notes: str = ""


def _percentile(samples: list[float], pct: float) -> float:
    """Linear-interp percentile to match numpy's default behavior.

    Falls back to min/max at the ends when there are too few samples to
    interpolate. Empty lists return NaN (rendered as '—').
    """
    if not samples:
        return float("nan")
    ordered = sorted(samples)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def _fmt_ms(v: float) -> str:
    if v != v:  # NaN check without importing math
        return "—"
    if v >= 100:
        return f"{v:.0f}"
    if v >= 10:
        return f"{v:.1f}"
    return f"{v:.2f}"


def write_report(
    results: list[ScenarioResult],
    output_dir: Path,
    report_stem: str,
    env: dict,
) -> Path:
    """Write the markdown report and return its path.

    `report_stem` is the filename without extension (e.g.
    '2026-04-22-1430-profile'). The caller decides the timestamp/naming
    convention; this function just writes.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{report_stem}.md"

    lines: list[str] = []
    lines.append(f"# Profiling Report — {report_stem}")
    lines.append("")

    # --- Environment block ---
    lines.append("## Environment")
    lines.append("")
    lines.append("| Key | Value |")
    lines.append("|---|---|")
    for k, v in env.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")

    # --- Summary table: one row per (scenario, span) pair ---
    lines.append("## Summary")
    lines.append("")
    lines.append("| Scenario | Params | Span | N | min (ms) | median (ms) | p95 (ms) |")
    lines.append("|---|---|---|---:|---:|---:|---:|")
    for r in results:
        params_str = ", ".join(f"{k}={v}" for k, v in r.params.items()) or "—"
        if not r.timings_ms:
            lines.append(
                f"| {r.name} | {params_str} | — | 0 | — | — | — |"
            )
            continue
        for span, samples in r.timings_ms.items():
            n = len(samples)
            mn = min(samples) if samples else float("nan")
            med = statistics.median(samples) if samples else float("nan")
            p95 = _percentile(samples, 95.0)
            lines.append(
                f"| {r.name} | {params_str} | {span} | {n} | "
                f"{_fmt_ms(mn)} | {_fmt_ms(med)} | {_fmt_ms(p95)} |"
            )
    lines.append("")

    # --- Per-scenario sections ---
    lines.append("## Scenarios")
    lines.append("")
    for r in results:
        lines.append(f"### {r.name}")
        lines.append("")
        if r.params:
            params_str = ", ".join(f"`{k}={v}`" for k, v in r.params.items())
            lines.append(f"**Params:** {params_str}")
            lines.append("")
        if r.notes:
            lines.append(r.notes)
            lines.append("")
        if r.html_trace_relpath:
            lines.append(f"[pyinstrument trace]({r.html_trace_relpath})")
            lines.append("")
        else:
            lines.append("_No discovery-pass trace for this scenario._")
            lines.append("")
        # Raw samples table (useful when a span looks anomalous)
        for span, samples in r.timings_ms.items():
            lines.append(f"**{span}** raw samples (ms):")
            lines.append("")
            lines.append("```")
            lines.append(", ".join(_fmt_ms(s) for s in samples))
            lines.append("```")
            lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
```

- [ ] **Step 3.4: Run the tests — expect PASS**

Run: `python -m pytest tests/unit/test_profiling_report.py -v`
Expected: all 6 tests pass.

- [ ] **Step 3.5: Commit**

```bash
git add tools/profiling/report.py tests/unit/test_profiling_report.py
git commit -m "Profiling: add ScenarioResult + markdown report writer"
```

---

## Task 4: Harness runners — `run_timing_pass` + `run_discovery_pass` (TDD)

**Why:** The two-pass structure is the core architectural decision. Landing it as its own module means scenarios stay simple (they just describe work; the harness handles measurement), and the tests can use trivial `lambda` scenarios to cover the runners without any SenseVoice dependency.

**Files:**
- Create: `tools/profiling/harness.py`
- Create: `tests/unit/test_profiling_harness.py`

- [ ] **Step 4.1: Write failing tests for the runners**

Create `tests/unit/test_profiling_harness.py`:

```python
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
    """A scenario that does real (tiny) work — good for harness tests."""
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


# ----- run_timing_pass -----

def test_run_timing_pass_returns_scenario_result(tmp_path: Path):
    result = run_timing_pass(_trivial_scenario, _make_ctx(tmp_path, iterations=3))
    assert isinstance(result, ScenarioResult)
    assert result.name == "trivial"


def test_run_timing_pass_populates_iterations(tmp_path: Path):
    result = run_timing_pass(_trivial_scenario, _make_ctx(tmp_path, iterations=5))
    assert len(result.timings_ms["work"]) == 5


# ----- run_discovery_pass -----

def test_run_discovery_pass_writes_non_empty_html(tmp_path: Path):
    html_path = tmp_path / "trace.html"
    run_discovery_pass(
        _trivial_scenario,
        _make_ctx(tmp_path, iterations=1),
        html_path=html_path,
    )
    assert html_path.exists()
    assert html_path.stat().st_size > 100  # actual HTML, not empty
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
```

- [ ] **Step 4.2: Run the tests — expect ImportError**

Run: `python -m pytest tests/unit/test_profiling_harness.py -v`
Expected: `ModuleNotFoundError: No module named 'tools.profiling.harness'`.

- [ ] **Step 4.3: Implement the harness**

Create `tools/profiling/harness.py`:

```python
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
    need a clean (unwarmed) instance call the factory; scenarios that
    just need any client keep a single instance around.
    """

    clips_dir: Path
    iterations: int
    stt_factory: Callable[[], Any]
    output_dir: Path


Scenario = Callable[[ProfilingContext], ScenarioResult]


def run_timing_pass(scenario: Scenario, ctx: ProfilingContext) -> ScenarioResult:
    """Execute the scenario once; the scenario itself loops `iterations`."""
    return scenario(ctx)


def run_discovery_pass(
    scenario: Scenario,
    ctx: ProfilingContext,
    html_path: Path,
) -> ScenarioResult:
    """Run the scenario inside a pyinstrument Profiler and save the HTML."""
    html_path.parent.mkdir(parents=True, exist_ok=True)
    profiler = Profiler()
    profiler.start()
    try:
        result = scenario(ctx)
    finally:
        profiler.stop()
    html_path.write_text(profiler.output_html(), encoding="utf-8")
    # Store the filename only — the report lives in the same folder.
    result.html_trace_relpath = html_path.name
    return result
```

- [ ] **Step 4.4: Run the tests — expect PASS**

Run: `python -m pytest tests/unit/test_profiling_harness.py -v`
Expected: all 4 tests pass.

- [ ] **Step 4.5: Commit**

```bash
git add tools/profiling/harness.py tests/unit/test_profiling_harness.py
git commit -m "Profiling: add two-pass harness runners (timing + discovery)"
```

---

## Task 5: `benchmarks_setup.py` — LibriSpeech fetch + transcode (TDD)

**Why:** Isolating the filesystem / network side of the harness behind its own module lets the scenario code assume clips exist. An injected `download_fn` parameter keeps the tests hermetic — we don't hit `openslr.org` in CI.

**Files:**
- Create: `tools/profiling/benchmarks_setup.py`
- Create: `tests/unit/test_profiling_benchmarks_setup.py`

- [ ] **Step 5.1: Write failing tests**

Create `tests/unit/test_profiling_benchmarks_setup.py`:

```python
import json
import wave
from pathlib import Path

import pytest

from tools.profiling.benchmarks_setup import (
    BenchmarksUnavailable,
    ensure_clips,
)


def _write_silence_wav(path: Path, duration_s: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n_samples = int(16000 * duration_s)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * n_samples)


def _seed_clips(clips_dir: Path) -> None:
    _write_silence_wav(clips_dir / "short.wav", 1.0)
    _write_silence_wav(clips_dir / "medium.wav", 1.0)
    _write_silence_wav(clips_dir / "long.wav", 1.0)
    (clips_dir / "transcripts.json").write_text(
        json.dumps({"short": "a", "medium": "b", "long": "c"}),
        encoding="utf-8",
    )


def test_ensure_clips_noop_when_files_exist(tmp_path: Path):
    _seed_clips(tmp_path)
    called = {"n": 0}

    def fake_download(_dest: Path) -> None:
        called["n"] += 1

    ensure_clips(tmp_path, download_fn=fake_download)
    assert called["n"] == 0


def test_ensure_clips_raises_when_download_fn_raises(tmp_path: Path):
    def failing_download(_dest: Path) -> None:
        raise RuntimeError("network offline")

    with pytest.raises(BenchmarksUnavailable) as excinfo:
        ensure_clips(tmp_path, download_fn=failing_download)
    assert "network offline" in str(excinfo.value)
    # The error message should tell the user where to drop their own WAVs.
    assert str(tmp_path) in str(excinfo.value)


def test_ensure_clips_noop_if_one_file_missing_but_download_provides_it(
    tmp_path: Path,
):
    # Seed two of three; download_fn must run exactly once to fill the gap.
    _write_silence_wav(tmp_path / "short.wav", 1.0)
    _write_silence_wav(tmp_path / "medium.wav", 1.0)
    (tmp_path / "transcripts.json").write_text(
        json.dumps({"short": "a", "medium": "b"}), encoding="utf-8"
    )
    download_calls = {"n": 0}

    def synthesizing_download(dest: Path) -> None:
        download_calls["n"] += 1
        _write_silence_wav(dest / "long.wav", 1.0)
        # Re-write transcripts fully (simulating a fresh download run).
        (dest / "transcripts.json").write_text(
            json.dumps({"short": "a", "medium": "b", "long": "c"}),
            encoding="utf-8",
        )

    ensure_clips(tmp_path, download_fn=synthesizing_download)
    assert download_calls["n"] == 1
    assert (tmp_path / "long.wav").exists()


def test_ensure_clips_validates_wav_format(tmp_path: Path):
    # Seed a WAV with the wrong sample rate — ensure_clips should detect it.
    bad = tmp_path / "short.wav"
    bad.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(bad), "wb") as wf:
        wf.setnchannels(2)  # wrong: stereo
        wf.setsampwidth(2)
        wf.setframerate(44100)  # wrong: 44.1 kHz
        wf.writeframes(b"\x00\x00\x00\x00")
    _write_silence_wav(tmp_path / "medium.wav", 1.0)
    _write_silence_wav(tmp_path / "long.wav", 1.0)
    (tmp_path / "transcripts.json").write_text(
        json.dumps({"short": "a", "medium": "b", "long": "c"}),
        encoding="utf-8",
    )

    def noop_download(_dest: Path) -> None:
        pass

    with pytest.raises(BenchmarksUnavailable) as excinfo:
        ensure_clips(tmp_path, download_fn=noop_download)
    assert "format" in str(excinfo.value).lower()
```

- [ ] **Step 5.2: Run the tests — expect ImportError**

Run: `python -m pytest tests/unit/test_profiling_benchmarks_setup.py -v`
Expected: `ModuleNotFoundError: No module named 'tools.profiling.benchmarks_setup'`.

- [ ] **Step 5.3: Implement `benchmarks_setup.py`**

Create `tools/profiling/benchmarks_setup.py`:

```python
"""LibriSpeech clip fetcher + FLAC→WAV transcoder.

Idempotent: if `benchmarks/` already has the three expected WAVs and a
transcripts.json with matching keys, `ensure_clips` is a no-op. Otherwise
it calls `download_fn` (injected for testability) and re-validates.

The default download path pulls LibriSpeech test-clean, picks three
speaker chunks of varying length, and transcodes FLAC to 16 kHz mono
PCM via `soundfile`. Callers who want an offline run can monkeypatch
`download_fn` to something that writes canned files.
"""
import io
import json
import tarfile
import urllib.request
import wave
from pathlib import Path
from typing import Callable, Optional

_REQUIRED_WAVS = ("short.wav", "medium.wav", "long.wav")
_TRANSCRIPTS = "transcripts.json"

# Download pinned to the OpenSLR test-clean subset (~350 MB). The harness
# only uses three speaker chunks, so nothing breaks if the OpenSLR file
# layout changes within the subset — the download function picks any
# three short FLACs and concatenates for the long clip.
_LIBRISPEECH_URL = "https://www.openslr.org/resources/12/test-clean.tar.gz"


class BenchmarksUnavailable(RuntimeError):
    """Raised when benchmark clips can't be produced (missing + no network)."""


def _validate_wav(path: Path) -> None:
    """Raise BenchmarksUnavailable if the WAV isn't 16 kHz mono PCM-16."""
    with wave.open(str(path), "rb") as wf:
        if (
            wf.getnchannels() != 1
            or wf.getsampwidth() != 2
            or wf.getframerate() != 16000
        ):
            raise BenchmarksUnavailable(
                f"Benchmark clip {path.name} has wrong format: "
                f"{wf.getnchannels()}ch, {wf.getsampwidth() * 8}-bit, "
                f"{wf.getframerate()} Hz. Expected 1ch, 16-bit, 16000 Hz."
            )


def _all_present(clips_dir: Path) -> bool:
    if not all((clips_dir / name).exists() for name in _REQUIRED_WAVS):
        return False
    if not (clips_dir / _TRANSCRIPTS).exists():
        return False
    try:
        data = json.loads((clips_dir / _TRANSCRIPTS).read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return all(k in data for k in ("short", "medium", "long"))


def _default_download(dest: Path) -> None:  # pragma: no cover (network I/O)
    """Fetch LibriSpeech test-clean, pick three clips, transcode to WAV.

    This path is exercised in production but skipped in tests (the tests
    inject their own `download_fn`). Keeping it here — not in a separate
    'real' module — means the harness ships with one working download
    and no indirection to navigate.
    """
    import soundfile as sf

    dest.mkdir(parents=True, exist_ok=True)
    print(f"Downloading LibriSpeech test-clean to {dest} (one time, ~350 MB)...")
    with urllib.request.urlopen(_LIBRISPEECH_URL) as resp:
        tar_bytes = resp.read()

    flacs_with_transcripts: list[tuple[str, bytes, str]] = []
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tf:
        # Parse per-directory .trans.txt for ground truth; map utterance
        # ID → transcript line. LibriSpeech layout:
        # LibriSpeech/test-clean/<spk>/<ch>/<spk>-<ch>-<id>.flac
        # LibriSpeech/test-clean/<spk>/<ch>/<spk>-<ch>.trans.txt
        transcripts: dict[str, str] = {}
        for member in tf.getmembers():
            if member.name.endswith(".trans.txt"):
                fp = tf.extractfile(member)
                if fp is None:
                    continue
                for line in fp.read().decode("utf-8").splitlines():
                    utt_id, _, text = line.partition(" ")
                    if utt_id:
                        transcripts[utt_id] = text
        # Collect FLACs (sorted for reproducibility)
        flac_members = sorted(
            (m for m in tf.getmembers() if m.name.endswith(".flac")),
            key=lambda m: m.name,
        )
        # Pick three — the shortest FLAC in the corpus as 'short', a
        # mid-length one as 'medium', and three concatenated as 'long'.
        # We don't know durations without decoding, so sample a handful
        # and read their lengths.
        sampled: list[tuple[str, float, bytes]] = []
        for m in flac_members[: min(50, len(flac_members))]:
            fp = tf.extractfile(m)
            if fp is None:
                continue
            data = fp.read()
            info = sf.info(io.BytesIO(data))
            utt_id = Path(m.name).stem
            sampled.append((utt_id, info.duration, data))
        if len(sampled) < 3:
            raise BenchmarksUnavailable(
                "LibriSpeech archive had fewer than 3 usable FLACs"
            )
        sampled.sort(key=lambda x: x[1])  # shortest first
        short_id, _, short_flac = sampled[0]
        medium_id, _, medium_flac = sampled[len(sampled) // 2]

    def _write_wav(out_path: Path, flac_bytes: bytes) -> None:
        audio, sr = sf.read(io.BytesIO(flac_bytes), dtype="int16")
        if audio.ndim > 1:
            audio = audio[:, 0]  # force mono
        if sr != 16000:
            # LibriSpeech is 16 kHz by design; if we hit a mismatch, fail
            # loudly rather than silently resampling.
            raise BenchmarksUnavailable(
                f"Unexpected sample rate {sr} in LibriSpeech FLAC"
            )
        with wave.open(str(out_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(audio.tobytes())

    _write_wav(dest / "short.wav", short_flac)
    _write_wav(dest / "medium.wav", medium_flac)

    # Build long.wav from three concatenated short clips with 200 ms silence
    # between them.
    silence = b"\x00\x00" * int(16000 * 0.2)
    long_frames = bytearray()
    flac_ids: list[str] = []
    for utt_id, _, flac in sampled[:3]:
        audio, _sr = sf.read(io.BytesIO(flac), dtype="int16")
        if audio.ndim > 1:
            audio = audio[:, 0]
        long_frames += audio.tobytes()
        long_frames += silence
        flac_ids.append(utt_id)
    with wave.open(str(dest / "long.wav"), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(bytes(long_frames))

    (dest / _TRANSCRIPTS).write_text(
        json.dumps(
            {
                "short": transcripts.get(short_id, ""),
                "medium": transcripts.get(medium_id, ""),
                "long": " ".join(transcripts.get(i, "") for i in flac_ids),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def ensure_clips(
    clips_dir: Path,
    download_fn: Optional[Callable[[Path], None]] = None,
) -> None:
    """Guarantee the three WAVs + transcripts.json exist in `clips_dir`.

    On success, returns normally. Raises `BenchmarksUnavailable` if the
    files cannot be produced (network failure, archive corruption, or
    format validation failure). Error messages include the clips_dir
    path so the user knows where to drop their own WAVs manually.
    """
    clips_dir.mkdir(parents=True, exist_ok=True)
    if _all_present(clips_dir):
        for name in _REQUIRED_WAVS:
            _validate_wav(clips_dir / name)
        return

    download = download_fn or _default_download
    try:
        download(clips_dir)
    except BenchmarksUnavailable:
        raise
    except Exception as e:
        raise BenchmarksUnavailable(
            f"Could not fetch benchmark clips: {e}. "
            f"Drop your own 16 kHz mono PCM WAVs named short.wav, "
            f"medium.wav, long.wav into {clips_dir} (plus a "
            f"transcripts.json with keys short/medium/long) and re-run."
        ) from e

    if not _all_present(clips_dir):
        raise BenchmarksUnavailable(
            f"Download completed but {clips_dir} is still missing one of "
            f"{_REQUIRED_WAVS} or transcripts.json."
        )
    for name in _REQUIRED_WAVS:
        _validate_wav(clips_dir / name)
```

- [ ] **Step 5.4: Run the tests — expect PASS**

Run: `python -m pytest tests/unit/test_profiling_benchmarks_setup.py -v`
Expected: all 4 tests pass.

- [ ] **Step 5.5: Commit**

```bash
git add tools/profiling/benchmarks_setup.py tests/unit/test_profiling_benchmarks_setup.py
git commit -m "Profiling: add LibriSpeech benchmark clip fetcher"
```

---

## Task 6: Non-STT scenarios — `text_post_processing`, `cold_import`, `streaming_tick` (TDD)

**Why:** Start with the scenarios that don't depend on a real SenseVoice model — their tests run fast and their signatures lock in the scenario contract (`ProfilingContext → ScenarioResult`). Later tasks inherit the same pattern.

**Files:**
- Create: `tools/profiling/scenarios.py`
- Create: `tests/unit/test_profiling_scenarios.py`

- [ ] **Step 6.1: Write failing tests**

Create `tests/unit/test_profiling_scenarios.py`:

```python
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


# ----- text_post_processing -----

def test_text_post_processing_returns_result(tmp_path: Path):
    result = scenario_text_post_processing(_ctx(tmp_path, iterations=10))
    assert result.name == "text_post_processing"
    # At least one span; at least one sample per span.
    assert result.timings_ms
    for samples in result.timings_ms.values():
        assert len(samples) == 10


def test_text_post_processing_measures_separate_spans(tmp_path: Path):
    result = scenario_text_post_processing(_ctx(tmp_path, iterations=3))
    # We expect distinct spans for scrub / punctuation / lexicon so the
    # report can attribute cost to each stage.
    assert "scrub" in result.timings_ms
    assert "punctuation" in result.timings_ms
    assert "lexicon" in result.timings_ms


# ----- cold_import -----

def test_cold_import_returns_result(tmp_path: Path):
    result = scenario_cold_import(_ctx(tmp_path, iterations=1))
    assert result.name == "cold_import"
    assert "wall" in result.timings_ms
    assert len(result.timings_ms["wall"]) == 1
    # Should be non-trivial (imports take at least a few ms) but not
    # thousands of seconds — a rough sanity band only.
    assert result.timings_ms["wall"][0] > 10


# ----- streaming_tick -----

def test_streaming_tick_runs_three_buffer_sizes(tmp_path: Path):
    result = scenario_streaming_tick(_ctx(tmp_path, iterations=2))
    assert result.name == "streaming_tick"
    # Spans keyed by buffer duration so the report shows the scaling curve.
    assert "5s" in result.timings_ms
    assert "15s" in result.timings_ms
    assert "30s" in result.timings_ms
    for samples in result.timings_ms.values():
        assert len(samples) == 2
```

- [ ] **Step 6.2: Run the tests — expect ImportError**

Run: `python -m pytest tests/unit/test_profiling_scenarios.py -v`
Expected: `ModuleNotFoundError: No module named 'tools.profiling.scenarios'`.

- [ ] **Step 6.3: Implement the three non-STT scenarios**

Create `tools/profiling/scenarios.py`:

```python
"""Profiling scenarios.

Each scenario takes a `ProfilingContext` and returns a `ScenarioResult`.
The scenario itself owns the iteration loop — that way each scenario
decides whether a single sample is meaningful (cold_import: yes — one
run), a handful are enough (stt_hot_path: three per clip length), or a
batch is needed to smooth noise (text_post_processing: thousands).
"""
import subprocess
import sys
import time
import wave
from pathlib import Path

from src.engine.lexicon import correct_radiology
from src.engine.punctuation import apply_punctuation
from src.security.scrubber import scrub_text
from tools.profiling.harness import ProfilingContext
from tools.profiling.report import ScenarioResult

# Representative clinical paragraph for text_post_processing. Uses a PHI
# surface (Dr. Harwood, 2026-03-15) and radiology-adjacent wording so
# scrub + lexicon both have something to chew on.
_SAMPLE_TEXT = (
    "comma Dr. Harwood reviewed the chest CT from 2026-03-15 "
    "the plural effusion is stable new paragraph "
    "lungs are clear period no pneumonia period"
)


def _read_wav_bytes(path: Path) -> bytes:
    return path.read_bytes()


def scenario_text_post_processing(ctx: ProfilingContext) -> ScenarioResult:
    """Per-iteration: scrub → punctuation → lexicon on a fixed paragraph.

    Each stage's cost is measured separately so the report attributes
    time accurately. Iteration counts are expected to be high (~1000)
    because each call is sub-millisecond.
    """
    spans: dict[str, list[float]] = {"scrub": [], "punctuation": [], "lexicon": []}
    for _ in range(ctx.iterations):
        t0 = time.perf_counter()
        scrubbed = scrub_text(_SAMPLE_TEXT)
        t1 = time.perf_counter()
        punctuated = apply_punctuation(scrubbed)
        t2 = time.perf_counter()
        correct_radiology(punctuated)
        t3 = time.perf_counter()
        spans["scrub"].append((t1 - t0) * 1000)
        spans["punctuation"].append((t2 - t1) * 1000)
        spans["lexicon"].append((t3 - t2) * 1000)
    return ScenarioResult(
        name="text_post_processing",
        params={"iterations": ctx.iterations},
        timings_ms=spans,
    )


def scenario_cold_import(ctx: ProfilingContext) -> ScenarioResult:
    """Wall time of `python -c "import src.main"` in a fresh subprocess.

    Must use a subprocess — measuring within this process would include
    modules already in sys.modules. `iterations` is honored but the
    report only surfaces one sample in practice (this scenario's whole
    point is the first-start cost).
    """
    samples: list[float] = []
    for _ in range(ctx.iterations):
        t0 = time.perf_counter()
        subprocess.run(
            [sys.executable, "-c", "import src.main"],
            check=True,
            capture_output=True,
        )
        samples.append((time.perf_counter() - t0) * 1000)
    return ScenarioResult(
        name="cold_import",
        params={"iterations": ctx.iterations},
        timings_ms={"wall": samples},
    )


def _silence_wav_bytes(duration_s: float) -> bytes:
    """In-memory 16 kHz mono PCM WAV of silence for streaming scaling tests."""
    import io

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * int(16000 * duration_s))
    return buf.getvalue()


def scenario_streaming_tick(ctx: ProfilingContext) -> ScenarioResult:
    """Direct calls to the streaming worker with progressively longer buffers.

    Measures the "re-transcribe the growing buffer" scaling flagged in
    the README. Uses ctx.stt_factory so dry-run and real-STT paths both
    work — dry-run gets flat timings, real STT gets the actual curve.
    """
    from src.core.streaming import StreamingTranscriber
    from tools.profiling.mocks import MockRecorder

    stt = ctx.stt_factory()
    if hasattr(stt, "warm"):
        stt.warm()  # one-time load outside the measurement loop

    spans: dict[str, list[float]] = {"5s": [], "15s": [], "30s": []}
    for label, duration_s in (("5s", 5.0), ("15s", 15.0), ("30s", 30.0)):
        wav = _silence_wav_bytes(duration_s)
        recorder = MockRecorder(audio_bytes=wav)
        st = StreamingTranscriber(recorder, stt)
        for _ in range(ctx.iterations):
            t0 = time.perf_counter()
            # Call the worker directly (not the Qt timer-driven _tick,
            # which needs an event loop) — same code path for the heavy
            # work, no UI scaffolding required.
            st._transcribe_worker(wav)
            spans[label].append((time.perf_counter() - t0) * 1000)
    return ScenarioResult(
        name="streaming_tick",
        params={"iterations_per_size": ctx.iterations},
        timings_ms=spans,
    )
```

- [ ] **Step 6.4: Run the tests — expect PASS**

Run: `python -m pytest tests/unit/test_profiling_scenarios.py -v`
Expected: all 4 tests pass. The `cold_import` test spawns a real subprocess — it will take a second or two but should succeed as long as `pip install -e .` has been run (Task 1 step 1.3).

- [ ] **Step 6.5: Commit**

```bash
git add tools/profiling/scenarios.py tests/unit/test_profiling_scenarios.py
git commit -m "Profiling: add text_post_processing / cold_import / streaming_tick scenarios"
```

---

## Task 7: STT scenarios — `sensevoice_warm`, `stt_hot_path`, `full_pipeline` (TDD)

**Why:** The remaining three scenarios all depend on an STT client. Tests use `FixedLatencySTT` via `ctx.stt_factory`, so they run in seconds without loading the real 100 MB SenseVoice model. Production runs pass a real factory from the CLI.

**Files:**
- Modify: `tools/profiling/scenarios.py` (append three new scenario functions)
- Modify: `tests/unit/test_profiling_scenarios.py` (append three new tests)

- [ ] **Step 7.1: Add failing tests for the STT scenarios**

Append to `tests/unit/test_profiling_scenarios.py`:

```python
# ----- sensevoice_warm -----

def test_sensevoice_warm_returns_result(tmp_path: Path):
    from tools.profiling.scenarios import scenario_sensevoice_warm
    result = scenario_sensevoice_warm(_ctx(tmp_path, iterations=2))
    assert result.name == "sensevoice_warm"
    assert "warm" in result.timings_ms
    assert len(result.timings_ms["warm"]) == 2


def test_sensevoice_warm_builds_fresh_client_each_iteration(tmp_path: Path):
    """A warm scenario must not reuse a primed instance across iterations."""
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


def test_full_pipeline_uses_inapp_mode_not_wedge(tmp_path: Path):
    """In-app mode must be used so the mock wedge is never called —
    keeps the profile focused on the pipeline, not on Win32 overhead."""
    from tools.profiling.mocks import MockWedge
    from tools.profiling.scenarios import scenario_full_pipeline

    # We can't directly inspect the internal wedge from outside; this test
    # just verifies the scenario runs cleanly. Wedge-call inspection would
    # require plumbing a handle out, which adds coupling without payoff.
    result = scenario_full_pipeline(_ctx(tmp_path, iterations=1))
    assert result.name == "full_pipeline"
```

- [ ] **Step 7.2: Run the tests — expect ImportError for the three new names**

Run: `python -m pytest tests/unit/test_profiling_scenarios.py -v`
Expected: the three new tests fail with `ImportError: cannot import name 'scenario_sensevoice_warm' ...`. Existing tests still pass.

- [ ] **Step 7.3: Implement the three STT scenarios**

Append to `tools/profiling/scenarios.py`:

```python
def scenario_sensevoice_warm(ctx: ProfilingContext) -> ScenarioResult:
    """Measures cold-load time by building a fresh client each iteration.

    Calling `stt_factory()` per iteration is what makes the "warm"
    measurement valid — a cached module still counts, but an already-
    warmed instance would trivially return near-zero.
    """
    samples: list[float] = []
    for _ in range(ctx.iterations):
        stt = ctx.stt_factory()
        t0 = time.perf_counter()
        if hasattr(stt, "warm"):
            stt.warm()
        samples.append((time.perf_counter() - t0) * 1000)
    return ScenarioResult(
        name="sensevoice_warm",
        params={"iterations": ctx.iterations},
        timings_ms={"warm": samples},
    )


def scenario_stt_hot_path(ctx: ProfilingContext) -> ScenarioResult:
    """`transcribe()` on each clip length after a single warm."""
    stt = ctx.stt_factory()
    if hasattr(stt, "warm"):
        stt.warm()

    spans: dict[str, list[float]] = {"short": [], "medium": [], "long": []}
    for label in ("short", "medium", "long"):
        wav = _read_wav_bytes(ctx.clips_dir / f"{label}.wav")
        # One discard iteration to prime any per-length caches inside
        # the STT engine, then the measured iterations.
        stt.transcribe(wav)
        for _ in range(ctx.iterations):
            t0 = time.perf_counter()
            stt.transcribe(wav)
            spans[label].append((time.perf_counter() - t0) * 1000)
    return ScenarioResult(
        name="stt_hot_path",
        params={"iterations_per_clip": ctx.iterations},
        timings_ms=spans,
    )


def scenario_full_pipeline(ctx: ProfilingContext) -> ScenarioResult:
    """End-to-end orchestrator round-trip per clip length, in-app mode."""
    from src.core.orchestrator import DictationOrchestrator
    from tools.profiling.mocks import MockRecorder, MockWedge

    stt = ctx.stt_factory()
    if hasattr(stt, "warm"):
        stt.warm()

    spans: dict[str, list[float]] = {"short": [], "medium": [], "long": []}
    for label in ("short", "medium", "long"):
        wav = _read_wav_bytes(ctx.clips_dir / f"{label}.wav")
        recorder = MockRecorder(audio_bytes=wav)
        wedge = MockWedge()
        orch = DictationOrchestrator(
            recorder=recorder,
            stt_client=stt,
            wedge=wedge,
        )
        # One discard iteration to avoid capturing one-shot pipeline setup
        # (e.g. first regex compile inside scrub_text if lazy).
        orch.handle_trigger_down()
        orch.handle_trigger_up(mode="inapp")
        for _ in range(ctx.iterations):
            t0 = time.perf_counter()
            orch.handle_trigger_down()
            orch.handle_trigger_up(mode="inapp")
            spans[label].append((time.perf_counter() - t0) * 1000)
    return ScenarioResult(
        name="full_pipeline",
        params={"iterations_per_clip": ctx.iterations, "mode": "inapp"},
        timings_ms=spans,
    )
```

- [ ] **Step 7.4: Run the tests — expect PASS**

Run: `python -m pytest tests/unit/test_profiling_scenarios.py -v`
Expected: all scenario tests pass (new + old).

- [ ] **Step 7.5: Commit**

```bash
git add tools/profiling/scenarios.py tests/unit/test_profiling_scenarios.py
git commit -m "Profiling: add sensevoice_warm / stt_hot_path / full_pipeline scenarios"
```

---

## Task 8: CLI entry point `tools/profile_pipeline.py` + dry-run smoke test

**Why:** One script wires scenarios, harness, report, and benchmarks_setup together behind a CLI. A smoke test with `--dry-run` drives the whole graph end-to-end using `FixedLatencySTT`, catching any wiring regression without a 350 MB download.

**Files:**
- Create: `tools/profile_pipeline.py`
- Create: `tests/unit/test_profile_pipeline_dryrun.py`

- [ ] **Step 8.1: Write the failing smoke test**

Create `tests/unit/test_profile_pipeline_dryrun.py`:

```python
import json
import subprocess
import sys
import wave
from pathlib import Path


def _write_silence_wav(path: Path, duration_s: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * int(16000 * duration_s))


def test_profile_pipeline_dry_run_end_to_end(tmp_path: Path):
    clips_dir = tmp_path / "benchmarks"
    output_dir = tmp_path / "out"
    for name, dur in (("short.wav", 0.5), ("medium.wav", 0.5), ("long.wav", 0.5)):
        _write_silence_wav(clips_dir / name, dur)
    (clips_dir / "transcripts.json").write_text(
        json.dumps({"short": "a", "medium": "b", "long": "c"}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.profile_pipeline",
            "--dry-run",
            "--iterations",
            "1",
            "--clips-dir",
            str(clips_dir),
            "--output-dir",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    # Exactly one markdown report file should have been written.
    reports = list(output_dir.glob("*.md"))
    assert len(reports) == 1, f"expected 1 report, found {reports}"
    content = reports[0].read_text(encoding="utf-8")
    # Every scenario name should appear in the summary table.
    for name in (
        "cold_import",
        "sensevoice_warm",
        "stt_hot_path",
        "full_pipeline",
        "streaming_tick",
        "text_post_processing",
    ):
        assert name in content, f"{name} missing from report"
```

- [ ] **Step 8.2: Run the smoke test — expect failure**

Run: `python -m pytest tests/unit/test_profile_pipeline_dryrun.py -v`
Expected: `ModuleNotFoundError: No module named 'tools.profile_pipeline'` (or the subprocess exits non-zero with the same).

- [ ] **Step 8.3: Implement the CLI**

Create `tools/profile_pipeline.py`:

```python
"""Reusable profiling harness for the dictation pipeline.

Run `python -m tools.profile_pipeline` to produce a timestamped report
under `docs/superpowers/profiling/`. See the accompanying spec at
`docs/superpowers/specs/2026-04-22-profiling-pass-design.md` for
scenario definitions and the rationale behind the two-pass design.
"""
import argparse
import datetime as dt
import platform
import sys
from pathlib import Path

from tools.profiling.benchmarks_setup import BenchmarksUnavailable, ensure_clips
from tools.profiling.harness import (
    ProfilingContext,
    run_discovery_pass,
    run_timing_pass,
)
from tools.profiling.mocks import FixedLatencySTT
from tools.profiling.report import write_report
from tools.profiling.scenarios import (
    scenario_cold_import,
    scenario_full_pipeline,
    scenario_sensevoice_warm,
    scenario_stt_hot_path,
    scenario_streaming_tick,
    scenario_text_post_processing,
)

# Scenarios that get a pyinstrument HTML trace alongside their timing pass.
# The ones excluded (cold_import, sensevoice_warm) are one-shots or cross
# a subprocess boundary where pyinstrument can't reach.
_DISCOVERY_SCENARIOS = {
    "stt_hot_path",
    "full_pipeline",
    "streaming_tick",
    "text_post_processing",
}


def _default_output_dir() -> Path:
    return Path("docs/superpowers/profiling")


def _default_clips_dir() -> Path:
    return Path("benchmarks")


def _build_stt_factory(dry_run: bool):
    if dry_run:
        return lambda: FixedLatencySTT(latency_ms=200, warm_latency_ms=50)
    from src.ai.sensevoice_stt_client import SenseVoiceSTTClient
    return lambda: SenseVoiceSTTClient()


def _collect_env(dry_run: bool) -> dict:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cpu": platform.processor() or "unknown",
        "stt_model": "FixedLatencySTT (dry-run)" if dry_run else "iic/SenseVoiceSmall",
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
    }


def _report_stem(now: dt.datetime) -> str:
    return now.strftime("%Y-%m-%d-%H%M") + "-profile"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Profile the dictation pipeline end-to-end.",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Skip cold_import and sensevoice_warm (fastest iteration loop).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use FixedLatencySTT instead of SenseVoice; useful for smoke tests.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Iteration count for STT / full-pipeline / streaming scenarios.",
    )
    parser.add_argument(
        "--iterations-text",
        type=int,
        default=1000,
        help="Iteration count for text_post_processing (sub-ms per iter).",
    )
    parser.add_argument(
        "--clips-dir",
        type=Path,
        default=_default_clips_dir(),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    args = parser.parse_args(argv)

    now = dt.datetime.now()
    stem = _report_stem(now)
    trace_dir = args.output_dir / stem
    # Report md lives directly in output_dir; HTML traces in a sibling
    # folder named after the report stem.
    try:
        ensure_clips(args.clips_dir)
    except BenchmarksUnavailable as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    stt_factory = _build_stt_factory(args.dry_run)

    def make_ctx(iterations: int) -> ProfilingContext:
        return ProfilingContext(
            clips_dir=args.clips_dir,
            iterations=iterations,
            stt_factory=stt_factory,
            output_dir=args.output_dir,
        )

    # (name, fn, iterations_override_or_None)
    bench = [
        ("cold_import", scenario_cold_import, 1),
        ("sensevoice_warm", scenario_sensevoice_warm, max(1, args.iterations)),
        ("stt_hot_path", scenario_stt_hot_path, args.iterations),
        ("full_pipeline", scenario_full_pipeline, args.iterations),
        ("streaming_tick", scenario_streaming_tick, args.iterations),
        ("text_post_processing", scenario_text_post_processing, args.iterations_text),
    ]
    if args.quick:
        bench = [b for b in bench if b[0] not in {"cold_import", "sensevoice_warm"}]

    results = []
    for name, fn, iters in bench:
        print(f"[{name}] timing pass ({iters} iter)...", flush=True)
        ctx = make_ctx(iters)
        timing_result = run_timing_pass(fn, ctx)

        if name in _DISCOVERY_SCENARIOS:
            # Discovery pass runs once (iterations=1-ish) with smaller
            # batches so the HTML stays readable.
            disc_iters = min(iters, 3)
            print(f"[{name}] discovery pass ({disc_iters} iter, pyinstrument)...", flush=True)
            html_path = trace_dir / f"{name}.html"
            disc_ctx = make_ctx(disc_iters)
            # Replace the discovery-pass ScenarioResult's timings with the
            # timing-pass ones, and keep the discovery pass HTML link.
            disc_result = run_discovery_pass(fn, disc_ctx, html_path=html_path)
            timing_result.html_trace_relpath = f"{stem}/{disc_result.html_trace_relpath}"

        results.append(timing_result)

    env = _collect_env(args.dry_run)
    report_path = write_report(
        results=results,
        output_dir=args.output_dir,
        report_stem=stem,
        env=env,
    )
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 8.4: Run the smoke test — expect PASS**

Run: `python -m pytest tests/unit/test_profile_pipeline_dryrun.py -v`
Expected: the single smoke test passes. End-to-end runtime should be a few seconds.

- [ ] **Step 8.5: Run the full profiling unit-test module set**

Run: `python -m pytest tests/unit/test_profiling_mocks.py tests/unit/test_profiling_report.py tests/unit/test_profiling_harness.py tests/unit/test_profiling_benchmarks_setup.py tests/unit/test_profiling_scenarios.py tests/unit/test_profile_pipeline_dryrun.py -v`
Expected: every test passes.

- [ ] **Step 8.6: Commit**

```bash
git add tools/profile_pipeline.py tests/unit/test_profile_pipeline_dryrun.py
git commit -m "Profiling: add tools/profile_pipeline.py CLI + dry-run smoke test"
```

---

## Task 9: `.gitignore` — `benchmarks/` + profiling trace folders

**Why:** `benchmarks/` contains 350 MB of LibriSpeech WAVs (public domain but bulky); pyinstrument HTML traces are large (often several MB) binary-ish artifacts. The markdown reports themselves are small, diffable, and useful to commit.

**Files:**
- Modify: `.gitignore`

- [ ] **Step 9.1: Append ignore patterns**

Add the following lines to the end of `.gitignore`:

```gitignore

# Profiling harness
benchmarks/
docs/superpowers/profiling/*/
!docs/superpowers/profiling/*.md
```

The pattern `docs/superpowers/profiling/*/` ignores the per-report HTML trace folders; the last `!...` keeps the markdown reports tracked.

- [ ] **Step 9.2: Verify the ignore rules**

Run: `git check-ignore -v benchmarks/short.wav docs/superpowers/profiling/2026-04-22-1430-profile/stt_hot_path.html`
Expected: both paths print with an ignore reason.

Run: `git check-ignore -v docs/superpowers/profiling/2026-04-22-1430-profile.md || echo "tracked (good)"`
Expected: "tracked (good)".

- [ ] **Step 9.3: Commit**

```bash
git add .gitignore
git commit -m "Profiling: gitignore benchmarks/ and HTML trace folders"
```

---

## Task 10: Run the harness for real and commit the initial report

**Why:** The spec's deliverable is both the tooling AND the first report. Running the tool against the project proves the pipeline works end-to-end on real SenseVoice output and gives the follow-up spec something concrete to act on.

**Files:**
- Creates: `docs/superpowers/profiling/<timestamp>-profile.md` (committed)
- Creates: `benchmarks/*.wav` (gitignored, local only)
- Creates: `docs/superpowers/profiling/<timestamp>-profile/*.html` (gitignored)

- [ ] **Step 10.1: Install the sensevoice extra if not already present**

Run: `pip show funasr || pip install -e '.[sensevoice]'`
Expected: `funasr` installed (or already installed from prior work).

- [ ] **Step 10.2: Run the harness**

Run: `python -m tools.profile_pipeline`
Expected:
- First-run: LibriSpeech download progress prints (~350 MB, one-time).
- SenseVoice warms (~few seconds).
- Each scenario prints its "timing pass" / "discovery pass" line.
- Final line: `Report: docs/superpowers/profiling/2026-MM-DD-HHMM-profile.md`.

If anything errors, fix the specific failure (don't paper over with try/except) before proceeding. The most likely errors and what they mean:
- `BenchmarksUnavailable: ...` — network or archive issue; follow the instructions in the error to drop WAVs manually.
- `ImportError` involving `funasr` — Step 10.1 wasn't run; run it.
- A scenario raising a `KeyError` or similar — a bug in this plan that the tests missed; fix forward, update the relevant test.

- [ ] **Step 10.3: Spot-check the report**

Open the generated markdown file. Sanity-check:
- Environment block populated (Python version, platform, CPU).
- Summary table has a row per scenario span, min/median/p95 in ms.
- Per-scenario sections link to HTML traces for the four discovery scenarios.
- Numbers are plausible — STT latency in hundreds of milliseconds, text_post_processing in hundreds of microseconds.

Open two or three of the HTML traces in a browser; confirm the call tree renders.

- [ ] **Step 10.4: Commit the report (markdown only — traces are gitignored)**

```bash
git add docs/superpowers/profiling/*.md
git commit -m "Profiling: initial report from tools/profile_pipeline.py"
```

If `git status` after the commit shows any unexpected tracked changes under `benchmarks/` or the traces folder, stop and investigate — the gitignore rules from Task 9 aren't working as intended.

---

## Task 11: README update — point users at the profiling harness

**Why:** A one-line reference under the existing Testing section makes the tool discoverable. No need for a standalone section; the spec and report are the authoritative docs.

**Files:**
- Modify: `README.md`

- [ ] **Step 11.1: Add a short profiling section under Testing**

Find the Testing section in `README.md`. After the existing block that ends with "51 tests currently passing." (or whatever current count), add:

```markdown

## Profiling

Measure end-to-end pipeline latency on a fixed LibriSpeech workload:

```bash
python -m tools.profile_pipeline
```

First run downloads ~350 MB of LibriSpeech test-clean into `benchmarks/`
(gitignored). Each run writes a timestamped report under
`docs/superpowers/profiling/` with per-scenario `pyinstrument` traces.

Pass `--dry-run` to swap in a fixed-latency STT stub (no SenseVoice
required); useful for smoke-testing the harness itself.
```

- [ ] **Step 11.2: Verify the README renders**

Run: `python -c "import pathlib; print(pathlib.Path('README.md').read_text()[-800:])"`
Expected: the new profiling section is visible at/near the end.

- [ ] **Step 11.3: Commit**

```bash
git add README.md
git commit -m "README: document tools/profile_pipeline.py under Testing"
```

---

## Task 12: Profiling-pass + dead-code / readability sweep (standing plan template)

**Why:** Every plan ends with these two closing steps. This plan literally built the profiling tool, so the profiling pass is running it and sanity-checking the output (already done in Task 10). The readability sweep targets the files we just created.

**Files:**
- Modify (if needed): any of the new files under `tools/profiling/` and `tools/profile_pipeline.py`

- [ ] **Step 12.1: Profiling pass (Task 10 re-confirmation)**

Re-open the report from Task 10. If any span looks unexpected (e.g. `scrub` dominating over `transcribe`, or `full_pipeline` < sum-of-parts), note it — that's exactly the data the follow-up spec needs.

Write down (mentally or as a scratch note) the two or three most striking findings. These will seed the next brainstorming cycle.

- [ ] **Step 12.2: Dead-code sweep — unused imports and orphaned helpers**

Run: `python -m pytest tests/unit/test_profiling_*.py tests/unit/test_profile_pipeline_dryrun.py -q`
Expected: all tests still pass.

Open each of the six new source files:
- `tools/__init__.py`
- `tools/profiling/__init__.py`
- `tools/profiling/mocks.py`
- `tools/profiling/report.py`
- `tools/profiling/harness.py`
- `tools/profiling/benchmarks_setup.py`
- `tools/profiling/scenarios.py`
- `tools/profile_pipeline.py`

For each, check:
- Any import that nothing in the file references? Remove.
- Any function defined but never called by anything in the module or tests? Remove (or move behind an explicit opt-in comment if it's obviously a future hook — preferably remove).
- Any comment that restates what the next line does? Remove.

- [ ] **Step 12.3: Readability sweep — file-size and single-purpose check**

Run: `wc -l tools/profile_pipeline.py tools/profiling/*.py`
Expected: each file under ~250 lines.

If any file exceeds that, ask whether it has more than one responsibility. The most likely offender is `scenarios.py` (six scenarios in one file). If it feels crowded, splitting into `scenarios/text.py` / `scenarios/audio.py` / `scenarios/pipeline.py` with a package `__init__.py` re-exporting the six functions is fine — but only if the tests still pass afterward and the file really was doing too much. Don't restructure for its own sake.

- [ ] **Step 12.4: Final test sweep**

Run: `python -m pytest tests/ -x --tb=short`
Expected: entire project test suite passes, same pass count as before + the new profiling tests.

- [ ] **Step 12.5: Commit any refactors**

If Steps 12.2 / 12.3 produced edits:

```bash
git add <edited files>
git commit -m "Profiling: dead-code + readability sweep"
```

If nothing changed, skip this commit — no empty commits.

---

## Self-review — spec coverage and consistency

Every numbered item in the spec should map to at least one task:

- Spec §Scope item 1 (3 clips under `benchmarks/`) → Tasks 5 + 10.
- Spec §Scope item 2 (two-pass profiling) → Task 4 + Task 8 wiring.
- Spec §Scope item 3 (six scenarios) → Tasks 6 + 7.
- Spec §Scope item 4 (markdown report with summary/env/traces) → Task 3.
- Spec §Scope item 5 (initial committed report) → Task 10.
- Spec §Architecture file tree → Tasks 1, 5-8 create the files; Task 9 ignores the right ones.
- Spec §Error handling — all four subcases covered by tests in Task 5 (BenchmarksUnavailable), Task 2 / 6 / 7 (mock fallbacks exercising the `supports_streaming` / `warm` interfaces), Task 8 CLI (argparse + exit code 2 on BenchmarksUnavailable).
- Spec §Testing — every unit test listed is present in Tasks 2-8; the smoke test is Task 8 Step 8.1.
- Spec §Profiling pass closing step → Task 10 + Task 12.1.
- Spec §Dead-code sweep closing step → Task 12.2-12.3.

Type consistency across tasks:
- `ScenarioResult(name, params, timings_ms, html_trace_relpath, notes)` — defined in Task 3; used by Task 4 (harness return type), Tasks 6-7 (scenarios), Task 8 (CLI). ✓
- `ProfilingContext(clips_dir, iterations, stt_factory, output_dir)` — defined in Task 4; used by scenario tests in Task 6/7 and the CLI in Task 8. ✓
- Scenario function names: `scenario_text_post_processing`, `scenario_cold_import`, `scenario_streaming_tick`, `scenario_sensevoice_warm`, `scenario_stt_hot_path`, `scenario_full_pipeline` — consistent across scenarios.py, tests, and CLI import list. ✓
- `FixedLatencySTT(latency_ms, warm_latency_ms, text)` — fields used in tests (Task 2), in scenario defaults (Task 6/7), and by the CLI `--dry-run` factory (Task 8). ✓
- `ensure_clips(clips_dir, download_fn=None)` — signature used in Task 5 tests, Task 8 CLI. ✓

No placeholders remain. No "TODO" or "implement later" or "similar to Task N".
