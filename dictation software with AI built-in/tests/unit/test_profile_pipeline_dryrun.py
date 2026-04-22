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
            "--iterations-text",
            "10",
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

    reports = list(output_dir.glob("*.md"))
    assert len(reports) == 1, f"expected 1 report, found {reports}"
    content = reports[0].read_text(encoding="utf-8")
    for name in (
        "cold_import",
        "sensevoice_warm",
        "stt_hot_path",
        "full_pipeline",
        "streaming_tick",
        "text_post_processing",
    ):
        assert name in content, f"{name} missing from report"
