import ctypes
from loguru import logger
from src.security.scrubber import scrub_text
from src.engine.punctuation import apply_punctuation
from src.engine.lexicon import correct_radiology


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
        # Optional streaming handle. When provided and in in-app mode,
        # the Stop path reads committed chunks via
        # `streaming.get_committed_snapshot()` and only transcribes the
        # remaining partial region — avoids re-doing the whole buffer.
        self.streaming = streaming
        # First wedge type of the process has no leading space; every
        # subsequent one gets a space prepended so click-on/click-off
        # dictation doesn't run sentences together in the target app.
        self._wedge_has_typed = False
        # Tracks whether the last wedge-mode output ended with a sentence
        # terminator. True initially so the very first session capitalizes.
        # In-app mode doesn't consult this — the caller uses editor context.
        self._wedge_last_terminator = True
        # When True, apply a radiology-vocabulary correction pass after
        # punctuation so near-misses like "plural" → "pleural" are fixed.
        # UI flips this via a checkbox; defaults on since the user is a
        # radiologist by default.
        self.radiology_mode = True

    def handle_trigger_down(self):
        """Called when the user presses the dictation button."""
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

        # 1. Transcribe (commit-aware for in-app mode).
        # In-app with prior commits: the UI's editor already contains the
        # committed chunks (from StreamingTranscriber.commit_ready). We
        # only need to transcribe + return the REMAINING partial region;
        # main.py passes that to commit_partial, which replaces just the
        # trailing partial — committed text stays put, no duplication.
        # Wedge mode and short dictations (no commits) fall back to the
        # whole-buffer transcribe since nothing has been displayed yet.
        committed_text: list[str] = []
        commit_idx = 0
        if mode == "inapp" and self.streaming is not None:
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

        # 3. Scrub PHI
        clean_text = scrub_text(raw_text)

        # 3b. Map spoken punctuation tokens (period, comma, new paragraph, ...).
        # Wedge mode uses our own terminator flag to decide first-letter caps;
        # in-app mode leaves the first letter alone and lets the UI layer
        # decide from editor context (cursor may have moved between sessions).
        cap_first = self._wedge_last_terminator if mode == "wedge" else False
        clean_text = apply_punctuation(clean_text, capitalize_first=cap_first)

        # 3c. Optional radiology-vocabulary correction.
        if self.radiology_mode:
            clean_text = correct_radiology(clean_text)
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

        return clean_text

    def generate_impression(self, findings: str) -> str:
        """
        Generates a radiology impression from findings text via the LLM client.
        Returns an empty string if no LLM client is configured.
        """
        if not self.llm_client:
            logger.warning("generate_impression called but no LLM client is configured.")
            return ""
        return self.llm_client.generate_impression(findings)
