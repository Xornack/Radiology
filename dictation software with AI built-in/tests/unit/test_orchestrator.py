from unittest.mock import MagicMock, patch
from src.core.orchestrator import DictationOrchestrator


def _make_orch(transcription: str = "hello world"):
    mock_recorder = MagicMock()
    mock_recorder.get_wav_bytes.return_value = b"wav"
    mock_whisper = MagicMock()
    mock_whisper.transcribe.return_value = transcription
    mock_wedge = MagicMock()
    return DictationOrchestrator(
        recorder=mock_recorder,
        stt_client=mock_whisper,
        wedge=mock_wedge,
    )


def test_handle_trigger_up_inapp_mode_does_not_call_wedge():
    """In-app mode routes text only to the caller, never to the wedge.

    In-app returns the text with its first letter LOWERCASED — the UI layer
    capitalizes based on editor context (whether the cursor sits after a
    sentence-terminator or not).
    """
    orch = _make_orch("Findings comma normal period")
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        result = orch.handle_trigger_up(mode="inapp")
    assert result == "findings, normal."
    orch.wedge.type_text.assert_not_called()


def test_handle_trigger_up_wedge_mode_calls_wedge_and_returns_text():
    """Wedge mode sends text via SendInput AND returns it for history display."""
    orch = _make_orch("Chest clear period")
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        result = orch.handle_trigger_up(mode="wedge")
    assert result == "Chest clear."
    orch.wedge.type_text.assert_called_once_with("Chest clear.")


def test_handle_trigger_up_wedge_mode_empty_text_skips_wedge():
    """Empty transcriptions must not be injected externally."""
    orch = _make_orch("")
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        result = orch.handle_trigger_up(mode="wedge")
    assert result == ""
    orch.wedge.type_text.assert_not_called()


def test_handle_trigger_up_defaults_to_inapp_mode():
    """Default mode must be 'inapp' so new callers don't accidentally emit keystrokes."""
    orch = _make_orch("hello")
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        orch.handle_trigger_up()
    orch.wedge.type_text.assert_not_called()


def test_wedge_second_session_prepends_space_separator():
    """Back-to-back click-on/click-off wedge sessions must not run sentences together.

    First call types as-is; every subsequent call gets a leading space so the
    terminator from the previous session doesn't hug the next sentence.
    """
    orch = _make_orch("Chest clear period")
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        orch.handle_trigger_up(mode="wedge")

    # Swap in new text for the second session
    orch.stt_client.transcribe.return_value = "No acute findings period"
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        orch.handle_trigger_up(mode="wedge")

    calls = [c.args[0] for c in orch.wedge.type_text.call_args_list]
    assert calls == ["Chest clear.", " No acute findings."]


def test_wedge_empty_second_session_does_not_flip_continuation_flag():
    """If a wedge session yields no text, the next one is still treated as a continuation
    only if something was actually typed before."""
    orch = _make_orch("")    # first session transcribes nothing
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        orch.handle_trigger_up(mode="wedge")
    orch.wedge.type_text.assert_not_called()

    orch.stt_client.transcribe.return_value = "Hello period"
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        orch.handle_trigger_up(mode="wedge")
    # Still the "first" typed call — no leading space.
    orch.wedge.type_text.assert_called_once_with("Hello.")


def test_wedge_mid_sentence_continuation_does_not_capitalize():
    """Wedge: session 1 ends without a terminator, session 2 must stay lowercase."""
    orch = _make_orch("the patient was examined")
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        orch.handle_trigger_up(mode="wedge")

    orch.stt_client.transcribe.return_value = "and no abnormalities"
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        orch.handle_trigger_up(mode="wedge")

    calls = [c.args[0] for c in orch.wedge.type_text.call_args_list]
    assert calls == ["The patient was examined", " and no abnormalities"]


def test_wedge_after_terminator_capitalizes_next_session():
    """Wedge: session 1 ends with '.', session 2's first letter must be capitalized."""
    orch = _make_orch("clear period")
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        orch.handle_trigger_up(mode="wedge")

    orch.stt_client.transcribe.return_value = "no acute findings period"
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        orch.handle_trigger_up(mode="wedge")

    calls = [c.args[0] for c in orch.wedge.type_text.call_args_list]
    assert calls == ["Clear.", " No acute findings."]


def test_wedge_after_question_mark_capitalizes_next_session():
    """Question mark is also a sentence terminator for the continuation flag."""
    orch = _make_orch("is it clear question mark")
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        orch.handle_trigger_up(mode="wedge")

    orch.stt_client.transcribe.return_value = "yes period"
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        orch.handle_trigger_up(mode="wedge")

    calls = [c.args[0] for c in orch.wedge.type_text.call_args_list]
    assert calls == ["Is it clear?", " Yes."]


def test_inapp_result_is_lowercased_first_letter():
    """In-app always returns text with first letter lowered; UI decides caps."""
    orch = _make_orch("clear period")
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        result = orch.handle_trigger_up(mode="inapp")
    assert result == "clear."


def test_radiology_mode_corrects_plural_to_pleural():
    """When radiology_mode is on, 'plural' in the transcript becomes 'pleural'."""
    orch = _make_orch("large plural effusion period")
    orch.radiology_mode = True
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        result = orch.handle_trigger_up(mode="inapp")
    assert "pleural" in result
    assert "plural" not in result


def test_radiology_mode_off_leaves_text_untouched_by_lexicon():
    """When radiology_mode is off, near-miss radiology words pass through verbatim."""
    orch = _make_orch("large plural effusion period")
    orch.radiology_mode = False
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        result = orch.handle_trigger_up(mode="inapp")
    # Should still produce "plural" (not corrected) because the vocab pass is off.
    assert "plural" in result


def test_radiology_mode_defaults_on():
    """A fresh orchestrator runs with radiology mode on — user is a radiologist."""
    orch = _make_orch("")
    assert orch.radiology_mode is True


class FakeStreamingHandle:
    """Stand-in for StreamingTranscriber's snapshot accessor only."""

    def __init__(self, committed_text: list, commit_sample_idx: int):
        self._committed_text = committed_text
        self._commit_sample_idx = commit_sample_idx

    def get_committed_snapshot(self):
        return list(self._committed_text), self._commit_sample_idx


def _mk_orch_with_streaming(
    committed: list,
    commit_idx: int,
    remaining_transcription: str = "and no fever",
    buffer_end_sample: int = 100000,
):
    recorder = MagicMock()
    recorder.get_sample_count.return_value = buffer_end_sample
    recorder.get_wav_bytes_slice.return_value = b"remaining-wav-bytes"
    recorder.get_wav_bytes.return_value = b"whole-buffer-wav-bytes"
    stt = MagicMock()
    stt.transcribe.return_value = remaining_transcription
    wedge = MagicMock()
    streaming = FakeStreamingHandle(committed, commit_idx)
    orch = DictationOrchestrator(
        recorder=recorder,
        stt_client=stt,
        wedge=wedge,
        streaming=streaming,
    )
    orch.radiology_mode = False
    return orch, recorder, stt, wedge


def test_stop_with_commits_returns_remainder_only():
    """In-app Stop with prior commits transcribes only the remainder and
    returns JUST the remainder text. The UI already has the committed
    chunks on-screen from StreamingTranscriber.commit_ready; returning
    the full concatenation here would cause the UI to duplicate them."""
    orch, recorder, stt, _ = _mk_orch_with_streaming(
        committed=["The patient has a cough"],
        commit_idx=47000,
        remaining_transcription="and no fever",
    )
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        result = orch.handle_trigger_up(mode="inapp")
    recorder.get_wav_bytes_slice.assert_called_once_with(47000, 100000)
    stt.transcribe.assert_called_once_with(b"remaining-wav-bytes")
    assert "no fever" in result.lower()
    assert "cough" not in result.lower()


def test_stop_without_commits_falls_through_to_whole_buffer():
    orch, recorder, stt, _ = _mk_orch_with_streaming(
        committed=[],
        commit_idx=0,
        remaining_transcription="The whole thing",
    )
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        result = orch.handle_trigger_up(mode="inapp")
    recorder.get_wav_bytes.assert_called_once()
    recorder.get_wav_bytes_slice.assert_not_called()
    assert "whole thing" in result


def test_stop_wedge_mode_uses_streaming_remainder():
    """Wedge Stop with prior streaming commits transcribes only the
    remainder and types it via the wedge. Committed chunks were already
    typed mid-session by type_wedge_commit; re-typing them would produce
    duplicate text in the external app."""
    orch, recorder, stt, wedge = _mk_orch_with_streaming(
        committed=["prior chunk"],
        commit_idx=50000,
        remaining_transcription="wedge transcription",
    )
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        orch.handle_trigger_up(mode="wedge")
    recorder.get_wav_bytes_slice.assert_called_once_with(50000, 100000)
    recorder.get_wav_bytes.assert_not_called()
    stt.transcribe.assert_called_once_with(b"remaining-wav-bytes")
    wedge.type_text.assert_called_once()


def test_stop_wedge_mode_without_commits_uses_whole_buffer():
    """Short wedge dictations that never reach a commit point still work:
    the Stop path falls through to the whole-buffer transcribe."""
    orch, recorder, stt, wedge = _mk_orch_with_streaming(
        committed=[],
        commit_idx=0,
        remaining_transcription="short one",
    )
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        orch.handle_trigger_up(mode="wedge")
    recorder.get_wav_bytes.assert_called_once()
    recorder.get_wav_bytes_slice.assert_not_called()
    wedge.type_text.assert_called_once()


def test_orchestrator_without_streaming_handle_works_as_today():
    recorder = MagicMock()
    recorder.get_wav_bytes.return_value = b"whole"
    stt = MagicMock()
    stt.transcribe.return_value = "hello"
    wedge = MagicMock()
    orch = DictationOrchestrator(
        recorder=recorder, stt_client=stt, wedge=wedge,
    )
    orch.radiology_mode = False
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        orch.handle_trigger_up(mode="inapp")
    recorder.get_wav_bytes.assert_called_once()


def test_handle_trigger_down_is_idempotent_while_recording():
    """A double-press must not restart the recorder mid-session (which
    would clear the audio buffer and lose the prior audio)."""
    orch = _make_orch()
    orch.handle_trigger_down()
    orch.handle_trigger_down()  # second press: ignored
    assert orch.recorder.start.call_count == 1


def test_handle_trigger_up_resets_recording_flag():
    """After Stop, a subsequent Start must work — the flag must clear."""
    orch = _make_orch()
    orch.handle_trigger_down()
    with patch("src.core.orchestrator.scrub_text", side_effect=lambda x: x):
        orch.handle_trigger_up(mode="inapp")
    orch.handle_trigger_down()
    assert orch.recorder.start.call_count == 2


# --- type_wedge_commit (mid-session commit streaming to wedge) -------------


def test_type_wedge_commit_empty_text_is_noop():
    """Empty / whitespace-less commits must never fire a wedge post."""
    orch = _make_orch()
    orch.type_wedge_commit("")
    orch.wedge.type_text.assert_not_called()


def test_type_wedge_commit_first_chunk_no_leading_space():
    """The very first commit in the process has no separator — the target
    field is assumed empty (or the user is placing the cursor)."""
    orch = _make_orch()
    orch.type_wedge_commit("the patient is stable")
    orch.wedge.type_text.assert_called_once_with("The patient is stable")


def test_type_wedge_commit_subsequent_chunk_prepends_space():
    """Mid-dictation continuation chunks must not run into the prior word."""
    orch = _make_orch()
    orch.type_wedge_commit("the patient is stable")
    orch.type_wedge_commit("and without pain")
    calls = [c.args[0] for c in orch.wedge.type_text.call_args_list]
    assert calls == ["The patient is stable", " and without pain"]


def test_type_wedge_commit_capitalizes_after_terminator():
    """First chunk caps (session-start terminator flag is True). Second
    chunk keeps lowercase unless the prior commit ended with . ? !."""
    orch = _make_orch()
    orch.type_wedge_commit("clear.")
    orch.type_wedge_commit("no acute findings.")
    calls = [c.args[0] for c in orch.wedge.type_text.call_args_list]
    assert calls == ["Clear.", " No acute findings."]


def test_type_wedge_commit_stays_lowercase_mid_sentence():
    """No capitalization when previous chunk did NOT end with a terminator."""
    orch = _make_orch()
    orch.type_wedge_commit("the patient was examined")
    orch.type_wedge_commit("and no abnormalities")
    calls = [c.args[0] for c in orch.wedge.type_text.call_args_list]
    assert calls == ["The patient was examined", " and no abnormalities"]


def test_type_wedge_commit_attaching_punctuation_skips_leading_space():
    """A lone attaching punctuation commit (from 'question mark') must
    hug the previous word: '...clear' + '?' → '...clear?', not '...clear ?'."""
    orch = _make_orch()
    orch.type_wedge_commit("is it clear")
    orch.type_wedge_commit("?")
    calls = [c.args[0] for c in orch.wedge.type_text.call_args_list]
    assert calls == ["Is it clear", "?"]


def test_type_wedge_commit_updates_terminator_flag():
    """Terminator flag must reflect the last non-space character typed so
    the Stop-path remainder uses the correct capitalize_first value."""
    orch = _make_orch()
    orch.type_wedge_commit("findings are clear.")
    assert orch._wedge_last_terminator is True
    orch.type_wedge_commit("the next clause")
    assert orch._wedge_last_terminator is False


def test_type_wedge_commit_wedge_failure_does_not_raise():
    """A wedge type_text failure must log and return — the streaming
    worker thread cannot be allowed to die on one bad commit."""
    orch = _make_orch()
    orch.wedge.type_text.side_effect = RuntimeError("post failed")
    orch.type_wedge_commit("hello")   # must not raise
    # Bookkeeping stays untouched on failure: the flag would be wrong for
    # the follow-up leading-space decision if we flipped it on a miss.
    assert orch._wedge_has_typed is False


def test_structure_report_delegates_to_llm_client():
    """Orchestrator.structure_report calls the LLM client's structure_report
    and returns its result."""
    mock_llm = MagicMock()
    mock_llm.structure_report.return_value = "EXAMINATION:\nCT chest.\n..."

    orchestrator = DictationOrchestrator(
        recorder=MagicMock(),
        stt_client=MagicMock(),
        wedge=MagicMock(),
        llm_client=mock_llm,
    )

    result = orchestrator.structure_report("freeform report text")

    assert "EXAMINATION" in result
    mock_llm.structure_report.assert_called_once_with("freeform report text")


def test_structure_report_returns_empty_when_no_llm_client():
    """Orchestrator with no llm_client returns "" without crashing."""
    orchestrator = DictationOrchestrator(
        recorder=MagicMock(),
        stt_client=MagicMock(),
        wedge=MagicMock(),
        llm_client=None,
    )

    result = orchestrator.structure_report("any text")
    assert result == ""
