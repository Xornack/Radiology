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

_LIBRISPEECH_URL = "https://www.openslr.org/resources/12/test-clean.tar.gz"


class BenchmarksUnavailable(RuntimeError):
    """Raised when benchmark clips can't be produced (missing + no network)."""


def _validate_wav(path: Path) -> None:
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
    """Fetch LibriSpeech test-clean, pick three clips, transcode to WAV."""
    import soundfile as sf

    dest.mkdir(parents=True, exist_ok=True)
    print(f"Downloading LibriSpeech test-clean to {dest} (one time, ~350 MB)...")
    with urllib.request.urlopen(_LIBRISPEECH_URL) as resp:
        tar_bytes = resp.read()

    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tf:
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
        flac_members = sorted(
            (m for m in tf.getmembers() if m.name.endswith(".flac")),
            key=lambda m: m.name,
        )
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
        sampled.sort(key=lambda x: x[1])
        short_id, _, short_flac = sampled[0]
        medium_id, _, medium_flac = sampled[len(sampled) // 2]

    def _write_wav(out_path: Path, flac_bytes: bytes) -> None:
        audio, sr = sf.read(io.BytesIO(flac_bytes), dtype="int16")
        if audio.ndim > 1:
            audio = audio[:, 0]
        if sr != 16000:
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
    """Guarantee the three WAVs + transcripts.json exist in `clips_dir`."""
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
