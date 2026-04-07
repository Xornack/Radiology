from src.security.scrubber import scrub_text
from loguru import logger

class DictationOrchestrator:
    """
    Coordinates the dictation workflow:
    HID Trigger -> Audio Recording -> Whisper STT -> PHI Scrubbing -> Keyboard Wedge.
    """
    def __init__(self, recorder, whisper_client, wedge, profiler=None):
        self.recorder = recorder
        self.whisper_client = whisper_client
        self.wedge = wedge
        self.profiler = profiler

    def handle_trigger_down(self):
        """
        Called when the user presses the dictation button.
        """
        logger.info("Dictation started.")
        if self.profiler:
            self.profiler.start("full_pipeline")
            self.profiler.start("audio_capture")
        self.recorder.start()

    def handle_trigger_up(self):
        """
        Called when the user releases the dictation button.
        """
        logger.info("Dictation stopped. Processing...")
        self.recorder.stop()
        if self.profiler:
            self.profiler.stop("audio_capture")
            self.profiler.start("whisper_stt")
        
        # 1. Get Audio Data
        audio_data = self.recorder.get_buffer()
        
        # 2. Transcribe
        raw_text = self.whisper_client.transcribe(audio_data)
        if self.profiler:
            self.profiler.stop("whisper_stt")
            self.profiler.start("scrubbing")
            
        # 3. Scrub PHI
        clean_text = scrub_text(raw_text)
        if self.profiler:
            self.profiler.stop("scrubbing")
            self.profiler.start("keyboard_wedge")
            
        # 4. Inject into Target App
        if clean_text:
            self.wedge.type_text(clean_text)
            
        if self.profiler:
            self.profiler.stop("keyboard_wedge")
            total = self.profiler.stop("full_pipeline")
            logger.info(f"Pipeline complete. Total Latency: {total:.4f}s")
        
        return clean_text
