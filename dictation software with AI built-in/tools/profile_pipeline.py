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
# cold_import crosses a subprocess boundary (pyinstrument can't reach);
# sensevoice_warm is effectively a one-shot and its HTML would be noisy.
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
        help="Use FixedLatencySTT instead of SenseVoice; for smoke-testing.",
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
        timing_result = run_timing_pass(fn, make_ctx(iters))

        if name in _DISCOVERY_SCENARIOS:
            disc_iters = min(iters, 3)
            print(
                f"[{name}] discovery pass ({disc_iters} iter, pyinstrument)...",
                flush=True,
            )
            html_path = trace_dir / f"{name}.html"
            disc_result = run_discovery_pass(fn, make_ctx(disc_iters), html_path=html_path)
            # Preserve timing-pass samples; only keep the HTML link from the
            # discovery pass.
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
