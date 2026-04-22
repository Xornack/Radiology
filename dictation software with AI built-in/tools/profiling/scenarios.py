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
