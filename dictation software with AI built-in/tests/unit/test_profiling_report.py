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
    assert "100" in content
    assert "300" in content


def test_report_links_to_html_trace_when_present(tmp_path: Path):
    out = write_report(
        results=_sample_results(),
        output_dir=tmp_path,
        report_stem="r",
        env=_sample_env(),
    )
    content = out.read_text(encoding="utf-8")
    assert "stt_hot_path_medium.html" in content
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
