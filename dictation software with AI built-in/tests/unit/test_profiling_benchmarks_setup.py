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
    assert str(tmp_path) in str(excinfo.value)


def test_ensure_clips_noop_if_one_file_missing_but_download_provides_it(
    tmp_path: Path,
):
    _write_silence_wav(tmp_path / "short.wav", 1.0)
    _write_silence_wav(tmp_path / "medium.wav", 1.0)
    (tmp_path / "transcripts.json").write_text(
        json.dumps({"short": "a", "medium": "b"}), encoding="utf-8"
    )
    download_calls = {"n": 0}

    def synthesizing_download(dest: Path) -> None:
        download_calls["n"] += 1
        _write_silence_wav(dest / "long.wav", 1.0)
        (dest / "transcripts.json").write_text(
            json.dumps({"short": "a", "medium": "b", "long": "c"}),
            encoding="utf-8",
        )

    ensure_clips(tmp_path, download_fn=synthesizing_download)
    assert download_calls["n"] == 1
    assert (tmp_path / "long.wav").exists()


def test_ensure_clips_validates_wav_format(tmp_path: Path):
    bad = tmp_path / "short.wav"
    bad.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(bad), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(44100)
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
