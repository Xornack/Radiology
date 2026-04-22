"""Markdown report writer for profiling runs.

Consumes a list of `ScenarioResult` objects (produced by the scenarios
module) and emits one `.md` file with a summary table and per-scenario
sections. pyinstrument HTML traces live next to the report and are
linked from their owning scenario section.
"""
import statistics
from dataclasses import dataclass
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
    """Linear-interp percentile (matches numpy default behavior).

    Empty → NaN (rendered '—'). Single-sample → that sample.
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
    if v != v:
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
    """Write the markdown report and return its path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{report_stem}.md"

    lines: list[str] = []
    lines.append(f"# Profiling Report — {report_stem}")
    lines.append("")

    lines.append("## Environment")
    lines.append("")
    lines.append("| Key | Value |")
    lines.append("|---|---|")
    for k, v in env.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Scenario | Params | Span | N | min (ms) | median (ms) | p95 (ms) |")
    lines.append("|---|---|---|---:|---:|---:|---:|")
    for r in results:
        params_str = ", ".join(f"{k}={v}" for k, v in r.params.items()) or "—"
        if not r.timings_ms:
            lines.append(f"| {r.name} | {params_str} | — | 0 | — | — | — |")
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
        for span, samples in r.timings_ms.items():
            lines.append(f"**{span}** raw samples (ms):")
            lines.append("")
            lines.append("```")
            lines.append(", ".join(_fmt_ms(s) for s in samples))
            lines.append("```")
            lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
