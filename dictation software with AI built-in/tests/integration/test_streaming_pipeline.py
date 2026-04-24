"""End-to-end streaming commit/split with mock recorder + STT.

Drives the new pipeline without Qt / microphone / real model. Uses
CommitSplitter directly (Qt-independent) and exercises the orchestrator
Stop path through its public interface.
"""
import io
import wave
from unittest.mock import patch

import numpy as np

from src.core.commit_splitter import CommitSplitter
from src.core.orchestrator import DictationOrchestrator


class ReplayRecorder:
    """Recorder double whose buffer grows over time under test control."""

    sample_rate = 16000
    channels = 1

    def __init__(self):
        self._samples = np.zeros(0, dtype=np.float32)

    def append(self, new_samples: np.ndarray) -> None:
        self._samples = np.concatenate([self._samples, new_samples])

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def get_sample_count(self) -> int:
        return int(self._samples.size)

    def get_wav_bytes_slice(self, start: int, end: int) -> bytes:
        if start < 0 or end < start or end > self._samples.size:
            raise ValueError(f"bad range: [{start}, {end}]")
        pcm = (self._samples[start:end] * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(pcm.tobytes())
        return buf.getvalue()

    def get_wav_bytes(self) -> bytes:
        return self.get_wav_bytes_slice(0, self._samples.size)


class ScriptedSTT:
    def __init__(self, script: list):
        self._script = list(script)
        self.calls: list[int] = []

    def transcribe(self, wav_bytes: bytes) -> str:
        with wave.open(io.BytesIO(wav_bytes)) as wf:
            self.calls.append(wf.getnframes())
        if not self._script:
            return ""
        return self._script.pop(0)


def _tone(duration_s: float, amplitude: float = 0.3) -> np.ndarray:
    t = np.arange(int(16000 * duration_s)) / 16000
    return (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def _silence(duration_s: float) -> np.ndarray:
    return np.zeros(int(16000 * duration_s), dtype=np.float32)


def test_streaming_pipeline_two_commits_then_stop():
    recorder = ReplayRecorder()
    stt = ScriptedSTT([
        "the patient has a cough",
        "and is febrile",
        "and is febrile today",
        "normal exam",
        "and no acute findings",
    ])
    splitter = CommitSplitter(recorder=recorder, stt_client=stt)

    recorder.append(np.concatenate([_tone(2.5), _silence(0.8), _tone(1.0)]))
    r1 = splitter.process_tick()
    assert r1.commit_text is not None
    assert "cough" in r1.commit_text.lower()
    assert r1.partial_text is not None
    assert "febrile" in r1.partial_text.lower()

    recorder.append(np.concatenate([_tone(1.5), _silence(0.8), _tone(0.8)]))
    r2 = splitter.process_tick()
    assert r2.commit_text is not None
    assert "febrile today" in r2.commit_text.lower()
    assert r2.partial_text is not None
    assert "normal exam" in r2.partial_text.lower()

    class FakeStreaming:
        def __init__(self, splitter):
            self._splitter = splitter

        def get_committed_snapshot(self):
            return self._splitter.get_committed_snapshot()

    orch = DictationOrchestrator(
        recorder=recorder,
        stt_client=stt,
        wedge=object(),
        streaming=FakeStreaming(splitter),
    )
    orch.radiology_mode = False
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        final = orch.handle_trigger_up(mode="inapp")
    # Orchestrator returns ONLY the remainder (UI already has committed
    # chunks on-screen via on_commit). Full text is reconstructed by the
    # UI as committed_chunks + final.
    committed, _ = splitter.get_committed_snapshot()
    assert any("cough" in c.lower() for c in committed)
    assert any("febrile today" in c.lower() for c in committed)
    assert "no acute findings" in final.lower()
    assert "cough" not in final.lower()


def test_streaming_pipeline_wedge_mode_types_each_commit():
    """End-to-end wedge streaming: each CommitSplitter commit → orchestrator
    type_wedge_commit → wedge.type_text. On Stop, only the remainder
    region is transcribed and typed. The committed chunks must NOT be
    re-typed (that would duplicate text in the external app)."""
    from unittest.mock import MagicMock

    recorder = ReplayRecorder()
    stt = ScriptedSTT([
        "the patient has a cough",         # tick 1 commit
        "and is febrile",                   # tick 1 partial (unused here)
        "and is febrile today",             # tick 2 commit
        "normal exam",                      # tick 2 partial (unused here)
        "and no acute findings",            # Stop-path remainder transcribe
    ])
    splitter = CommitSplitter(recorder=recorder, stt_client=stt)
    wedge = MagicMock()

    class FakeStreaming:
        def __init__(self, splitter):
            self._splitter = splitter

        def get_committed_snapshot(self):
            return self._splitter.get_committed_snapshot()

    orch = DictationOrchestrator(
        recorder=recorder,
        stt_client=stt,
        wedge=wedge,
        streaming=FakeStreaming(splitter),
    )
    orch.radiology_mode = False

    # Tick 1: produce a commit; forward it as main.py's dispatcher would.
    recorder.append(np.concatenate([_tone(2.5), _silence(0.8), _tone(1.0)]))
    r1 = splitter.process_tick()
    assert r1.commit_text is not None
    orch.type_wedge_commit(r1.commit_text)

    # Tick 2: another commit.
    recorder.append(np.concatenate([_tone(1.5), _silence(0.8), _tone(0.8)]))
    r2 = splitter.process_tick()
    assert r2.commit_text is not None
    orch.type_wedge_commit(r2.commit_text)

    # Stop: transcribe only the uncommitted remainder and type it.
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        final = orch.handle_trigger_up(mode="wedge")

    typed = [c.args[0] for c in wedge.type_text.call_args_list]
    # Exactly three posts: two commits + one remainder. No re-typing of
    # committed chunks (that would duplicate text in the external app).
    assert len(typed) == 3
    # First commit has no leading space (session start); every follow-up
    # that starts with a letter gets one.
    assert not typed[0].startswith(" ")
    assert typed[1].startswith(" ")
    assert typed[2].startswith(" ")
    # Final remainder matches what the orchestrator returned.
    assert typed[2].strip() == final.strip()
    assert "no acute findings" in final.lower()


def test_streaming_pipeline_no_commits_falls_back_to_whole_buffer():
    recorder = ReplayRecorder()
    recorder.append(_tone(2.0))
    stt = ScriptedSTT(["hello"])
    splitter = CommitSplitter(recorder=recorder, stt_client=stt)

    r = splitter.process_tick()
    assert r.commit_text is None
    assert r.partial_text == "hello"

    class FakeStreaming:
        def __init__(self, splitter):
            self._splitter = splitter

        def get_committed_snapshot(self):
            return self._splitter.get_committed_snapshot()

    stt_for_stop = ScriptedSTT(["hello again"])
    orch = DictationOrchestrator(
        recorder=recorder,
        stt_client=stt_for_stop,
        wedge=object(),
        streaming=FakeStreaming(splitter),
    )
    orch.radiology_mode = False
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        final = orch.handle_trigger_up(mode="inapp")
    assert "hello again" in final.lower()
