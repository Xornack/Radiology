import ctypes
from loguru import logger
from src.engine.pipeline import TextPipeline
# Re-exported for tests that patch `src.core.orchestrator.scrub_text`.
from src.security.scrubber import scrub_text  # noqa: F401


# Characters that typographically attach to the previous word. When a
# commit chunk begins with one (e.g. lone "?" from "question mark"), the
# continuation space must be skipped so we don't produce "clear ?".
_ATTACHING_PUNCTUATION = set('.,?!;:)]}"”')


def _foreground_window_title() -> str:
    """Best-effort retrieval of the currently-focused window title.

    Used only for diagnostic logging of the Wedge-mode PostMessageW target.
    Returns an empty string on any failure so logging never disrupts flow.
    """
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception:
        return ""


class DictationOrchestrator:
    """
    Coordinates the dictation workflow:
    HID Trigger -> Audio Recording -> Whisper STT -> PHI Scrubbing -> Keyboard Wedge.
    Optional LLM client enables AI impression generation on demand.
    """
    def __init__(
        self,
        recorder,
        stt_client,
        wedge,
        profiler=None,
        llm_client=None,
        streaming=None,
    ):
        self.recorder = recorder
        self.stt_client = stt_client
        self.wedge = wedge
        self.profiler = profiler
        self.llm_client = llm_client
        # Optional streaming handle. When provided, the Stop path reads
        # committed chunks via `streaming.get_committed_snapshot()` and
        # only transcribes the remaining partial region — both in-app
        # and wedge modes stream commits mid-session, so re-doing the
        # whole buffer on Stop would re-render/retype already-delivered
        # text.
        self.streaming = streaming
        # First wedge type of the process has no leading space; every
        # subsequent one gets a space prepended so click-on/click-off
        # dictation doesn't run sentences together in the target app.
        self._wedge_has_typed = False
        # Tracks whether the last wedge-mode output ended with a sentence
        # terminator. True initially so the very first session capitalizes.
        # In-app mode doesn't consult this — the caller uses editor context.
        self._wedge_last_terminator = True
        # Post-transcription text pipeline: scrub → punctuation → optional
        # radiology correction. Owned here so the three stages stay in sync
        # and the orchestrator doesn't have to know about them individually.
        self._text_pipeline = TextPipeline(radiology_mode=True)
        # Public knob the UI checkbox toggles; synced into the pipeline on
        # each call so mid-session rewiring is a no-op rather than stale.
        self.radiology_mode = True
        # Re-entrancy guard. A double-press of the trigger or a race between
        # UI button and hardware HID shouldn't restart the recorder mid-session
        # (which would clear the audio buffer and lose the dictation).
        self._recording = False

    def handle_trigger_down(self):
        """Called when the user presses the dictation button."""
        if self._recording:
            logger.warning("handle_trigger_down ignored: already recording")
            return
        self._recording = True
        logger.info("Dictation started.")
        if self.profiler:
            self.profiler.start("full_pipeline")
            self.profiler.start("audio_capture")
        self.recorder.start()

    def handle_trigger_up(self, mode: str = "inapp") -> str:
        """
        Process the recording and return the finalized text.

        `mode` selects the output sink:
          - "inapp":  text lands in the caller's UI editor (no external keystrokes).
          - "wedge":  text is also typed into the externally focused window via the wedge.
        The returned text is the same in both modes so the caller can display history.
        """
        logger.info("Dictation stopped. Processing...")
        self.recorder.stop()
        if self.profiler:
            self.profiler.stop("audio_capture")
            self.profiler.start("whisper_stt")

        # 1. Transcribe (commit-aware when streaming produced commits).
        # Both modes stream commits during recording:
        #   - In-app: commits land in the editor via window.on_commit.
        #   - Wedge:  commits are typed into the focused window via
        #             type_wedge_commit.
        # Either way, on Stop we only transcribe the REMAINING partial
        # region — the committed chunks are already on screen / typed.
        # Short dictations with no commits fall back to the whole buffer.
        committed_text: list[str] = []
        commit_idx = 0
        if self.streaming is not None:
            committed_text, commit_idx = self.streaming.get_committed_snapshot()

        if committed_text and commit_idx > 0:
            end_sample = self.recorder.get_sample_count()
            remainder_wav = self.recorder.get_wav_bytes_slice(commit_idx, end_sample)
            raw_text = self.stt_client.transcribe(remainder_wav)
        else:
            audio_bytes = self.recorder.get_wav_bytes()
            raw_text = self.stt_client.transcribe(audio_bytes)
        logger.debug(f"Whisper raw: {raw_text!r}")
        if self.profiler:
            self.profiler.stop("whisper_stt")
            self.profiler.start("scrubbing")

        # 3. Post-transcription text pipeline: scrub → punctuation → optional
        # radiology correction. Wedge mode uses the terminator flag for
        # first-letter caps; in-app leaves casing to the UI layer (which
        # decides from editor context — cursor may have moved between sessions).
        cap_first = self._wedge_last_terminator if mode == "wedge" else False
        self._text_pipeline.radiology_mode = self.radiology_mode
        # Engines that emit real punctuation (MedASR) must skip the Whisper
        # stripper — otherwise every `.` and `,` we produced disappears.
        # `is True` is deliberate: MagicMock STT stubs in tests auto-create a
        # truthy attribute here, and we want that to behave like a normal
        # Whisper-style engine unless the test opts in explicitly.
        emits_punct = getattr(self.stt_client, "emits_punctuation", False) is True
        clean_text = self._text_pipeline.process(
            raw_text,
            capitalize_first=cap_first,
            strip_inferred=not emits_punct,
        )
        logger.debug(f"Final text to send: {clean_text!r}")

        if self.profiler:
            self.profiler.stop("scrubbing")
            self.profiler.start("keyboard_wedge")

        # 4. Inject into external application only when explicitly requested
        if mode == "wedge" and clean_text:
            target = _foreground_window_title()
            to_type = (" " + clean_text) if self._wedge_has_typed else clean_text
            logger.info(
                f"Wedge mode: posting {len(to_type)} chars to focused window. "
                f"Foreground window: {target!r}"
            )
            try:
                self.wedge.type_text(to_type)
                self._wedge_has_typed = True
                self._wedge_last_terminator = clean_text.rstrip()[-1] in ".?!"
            except Exception as e:
                # Never let a wedge failure crash the UI handler —
                # the transcript is still returned for display
                logger.error(f"Keyboard wedge failed: {e}")

        if self.profiler:
            self.profiler.stop("keyboard_wedge")
            total = self.profiler.stop("full_pipeline")
            logger.info(f"Pipeline complete. Total latency: {total:.4f}s")

        self._recording = False
        return clean_text

    def type_wedge_commit(self, text: str) -> None:
        """Type one committed phrase to the wedge target mid-dictation.

        Wired to StreamingTranscriber.commit_ready in wedge mode. Tracks
        _wedge_has_typed and _wedge_last_terminator so the Stop-path
        remainder picks up matching leading-space/capitalization.
        """
        if not text:
            return
        # Commits arrive from CommitSplitter with capitalize_first=False.
        # Restore sentence-initial caps when the running state is at a
        # terminator (session start, or prior commit ended with . ? !).
        if self._wedge_last_terminator:
            text = text[0].upper() + text[1:]
        needs_space = (
            self._wedge_has_typed
            and text[0] not in _ATTACHING_PUNCTUATION
        )
        to_type = (" " + text) if needs_space else text
        try:
            self.wedge.type_text(to_type)
        except Exception as e:
            # A wedge failure here must not kill the streaming loop — next
            # tick will still fire. The transcript remains recoverable
            # from the recorder buffer on Stop.
            logger.error(f"Wedge commit failed: {e}")
            return
        self._wedge_has_typed = True
        stripped = text.rstrip()
        self._wedge_last_terminator = bool(stripped) and stripped[-1] in ".?!"

    def generate_impression(self, findings: str) -> str:
        """Ask the LLM client for an impression and time the round-trip.

        Returns "" if no LLM client is configured. The profiler timer
        logs cold-vs-warm Ollama latency so the user can see whether
        keep-alive tuning is needed.
        """
        if not self.llm_client:
            logger.warning(
                "generate_impression called but no LLM client is configured."
            )
            return ""
        if self.profiler:
            self.profiler.start("llm_impression")
        try:
            return self.llm_client.generate_impression(findings)
        finally:
            if self.profiler:
                total = self.profiler.stop("llm_impression")
                logger.info(f"Impression generation: {total:.2f}s")
