from loguru import logger
from src.security.scrubber import scrub_text
from src.engine.punctuation import apply_punctuation


class DictationOrchestrator:
    """
    Coordinates the dictation workflow:
    HID Trigger -> Audio Recording -> Whisper STT -> PHI Scrubbing -> Keyboard Wedge.
    Optional LLM client enables AI impression generation on demand.
    """
    def __init__(self, recorder, whisper_client, wedge, profiler=None, llm_client=None):
        self.recorder = recorder
        self.whisper_client = whisper_client
        self.wedge = wedge
        self.profiler = profiler
        self.llm_client = llm_client

    def handle_trigger_down(self):
        """Called when the user presses the dictation button."""
        logger.info("Dictation started.")
        if self.profiler:
            self.profiler.start("full_pipeline")
            self.profiler.start("audio_capture")
        self.recorder.start()

    def handle_trigger_up(self) -> str:
        """Called when the user releases the dictation button."""
        logger.info("Dictation stopped. Processing...")
        self.recorder.stop()
        if self.profiler:
            self.profiler.stop("audio_capture")
            self.profiler.start("whisper_stt")

        # 1. Get WAV bytes (correct format for Whisper)
        audio_bytes = self.recorder.get_wav_bytes()

        # 2. Transcribe
        raw_text = self.whisper_client.transcribe(audio_bytes)
        if self.profiler:
            self.profiler.stop("whisper_stt")
            self.profiler.start("scrubbing")

        # 3. Scrub PHI
        clean_text = scrub_text(raw_text)

        # 3b. Map spoken punctuation tokens (period, comma, new paragraph, ...).
        clean_text = apply_punctuation(clean_text)

        if self.profiler:
            self.profiler.stop("scrubbing")
            self.profiler.start("keyboard_wedge")

        # 4. Inject into target application
        if clean_text:
            try:
                self.wedge.type_text(clean_text)
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
