"""Profiling scenarios.

Each scenario takes a `ProfilingContext` and returns a `ScenarioResult`.
The scenario itself owns the iteration loop — that way each scenario
decides whether a single sample is meaningful (cold_import: yes — one
run), a handful are enough (stt_hot_path: three per clip length), or a
batch is needed to smooth noise (text_post_processing: thousands).
"""
import io
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
    """Per-iteration: scrub → punctuation → lexicon on a fixed paragraph."""
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

    Subprocess because measuring within this process would include modules
    already in sys.modules. Iterations are honored but 1 is typical.
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
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * int(16000 * duration_s))
    return buf.getvalue()


def scenario_sensevoice_warm(ctx: ProfilingContext) -> ScenarioResult:
    """Measures cold-load time by building a fresh client each iteration.

    Calling `stt_factory()` per iteration is what makes the "warm"
    measurement valid — an already-warmed instance would trivially
    return near-zero.
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
        # Discard iteration primes any per-length caches inside the STT.
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
        # Discard iteration so we don't capture one-shot pipeline setup.
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


def scenario_streaming_tick(ctx: ProfilingContext) -> ScenarioResult:
    """Per-tick work the StreamingTranscriber does, at 5/15/30 s buffers.

    Measures the "re-transcribe the growing buffer" scaling flagged in the
    README. Inlines the transcribe + apply_punctuation pair that
    StreamingTranscriber._transcribe_worker runs — bypassing the Qt
    QObject wrapper keeps the scenario hermetic from the Qt event loop
    (and from Qt DLL-load quirks that don't affect the work being
    measured).
    """
    stt = ctx.stt_factory()
    if hasattr(stt, "warm"):
        stt.warm()

    spans: dict[str, list[float]] = {"5s": [], "15s": [], "30s": []}
    for label, duration_s in (("5s", 5.0), ("15s", 15.0), ("30s", 30.0)):
        wav = _silence_wav_bytes(duration_s)
        for _ in range(ctx.iterations):
            t0 = time.perf_counter()
            text = stt.transcribe(wav)
            if text:
                apply_punctuation(text)
            spans[label].append((time.perf_counter() - t0) * 1000)
    return ScenarioResult(
        name="streaming_tick",
        params={"iterations_per_size": ctx.iterations},
        timings_ms=spans,
    )


def _tone_silence_pattern(total_s: float) -> bytes:
    """Synthesize a tone-silence-tone-... pattern WAV.

    440 Hz sine at amplitude 0.3, alternating 2.5 s tones with 600 ms
    silences, clipped to `total_s`. Ensures VAD has commit points to
    find roughly every 3 s.
    """
    import io

    import numpy as np

    sr = 16000
    chunks: list[np.ndarray] = []
    remaining = total_s
    tone_len = 2.5
    silence_len = 0.6
    t = np.arange(int(sr * tone_len)) / sr
    tone = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    silence = np.zeros(int(sr * silence_len), dtype=np.float32)
    while remaining > 0:
        if remaining >= tone_len:
            chunks.append(tone)
            remaining -= tone_len
        else:
            partial = (0.3 * np.sin(2 * np.pi * 440 * np.arange(int(sr * remaining)) / sr)).astype(np.float32)
            chunks.append(partial)
            remaining = 0
            break
        if remaining >= silence_len:
            chunks.append(silence)
            remaining -= silence_len
        else:
            chunks.append(np.zeros(int(sr * remaining), dtype=np.float32))
            remaining = 0
    all_samples = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    pcm = (all_samples * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def _wav_sample_count(wav_bytes: bytes) -> int:
    import io

    with wave.open(io.BytesIO(wav_bytes)) as wf:
        return wf.getnframes()


def _wav_slice(wav_bytes: bytes, start_sample: int, end_sample: int) -> bytes:
    import io

    with wave.open(io.BytesIO(wav_bytes)) as wf:
        if start_sample < 0 or end_sample < start_sample or end_sample > wf.getnframes():
            raise ValueError(f"bad slice [{start_sample}, {end_sample}]")
        wf.setpos(start_sample)
        frames = wf.readframes(end_sample - start_sample)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(frames)
    return buf.getvalue()


class _WavBackedRecorder:
    """Recorder shim for scenario_streaming_commit.

    Wraps a pre-rendered WAV so `get_sample_count` and
    `get_wav_bytes_slice` act on a fixed buffer. Uses real methods (not
    lambdas) so CommitSplitter's hasattr checks and error paths behave
    naturally.
    """

    def __init__(self, wav_bytes: bytes):
        self._wav = wav_bytes

    def get_sample_count(self) -> int:
        return _wav_sample_count(self._wav)

    def get_wav_bytes_slice(self, start: int, end: int) -> bytes:
        return _wav_slice(self._wav, start, end)


def scenario_streaming_commit(ctx: ProfilingContext) -> ScenarioResult:
    """Per-tick cost of the NEW streaming path (CommitSplitter).

    Uses a tone-silence-tone audio pattern so VAD has commit points to
    find. Measures one `process_tick()` call per iteration on 5 / 15 /
    30 s buffers. Paired with `scenario_streaming_tick` for before/after
    comparison in the report.
    """
    from src.core.commit_splitter import CommitSplitter

    stt = ctx.stt_factory()
    if hasattr(stt, "warm"):
        stt.warm()

    spans: dict[str, list[float]] = {"5s": [], "15s": [], "30s": []}
    for label, duration_s in (("5s", 5.0), ("15s", 15.0), ("30s", 30.0)):
        wav = _tone_silence_pattern(duration_s)
        for _ in range(ctx.iterations):
            # Fresh recorder + splitter per iteration: a commit from the
            # previous iteration mustn't shrink the next tick's partial.
            recorder = _WavBackedRecorder(wav)
            splitter = CommitSplitter(recorder=recorder, stt_client=stt)
            t0 = time.perf_counter()
            splitter.process_tick()
            spans[label].append((time.perf_counter() - t0) * 1000)
    return ScenarioResult(
        name="streaming_commit",
        params={"iterations_per_size": ctx.iterations},
        timings_ms=spans,
    )
