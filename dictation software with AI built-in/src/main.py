import sys
from PyQt6.QtWidgets import QApplication
from loguru import logger

from src.ui.main_window import MainWindow
from src.hardware.recorder import AudioRecorder
from src.hardware.mic_listener import MicListener
from src.ai.whisper_client import WhisperClient
from src.ai.llm_client import LLMClient
from src.core.orchestrator import DictationOrchestrator
from src.engine import wedge
from src.utils.profiler import LatencyTimer
from src.utils.settings import settings


def main():
    logger.info("Initializing Local AI Radiology Dictation Platform...")

    app = QApplication(sys.argv)

    # 1. Initialize AI clients from settings (env-configurable, no hardcoded URLs)
    whisper = WhisperClient(url=settings.whisper_url)
    llm = LLMClient(url=settings.llm_url)
    recorder = AudioRecorder()
    profiler = LatencyTimer()

    # 2. Setup Orchestrator (LLM client wired in for impression generation)
    orchestrator = DictationOrchestrator(
        recorder=recorder,
        whisper_client=whisper,
        wedge=wedge,
        profiler=profiler,
        llm_client=llm
    )

    # 3. Setup UI
    window = MainWindow()
    window.show()

    # 4. Setup Hardware Listener (VID/PID from env or defaults)
    mic = MicListener(
        vendor_id=settings.speechmike_vid,
        product_id=settings.speechmike_pid
    )

    def handle_mic_event(pressed: bool):
        if pressed:
            window.set_status("Recording...", "#f38ba8")   # red
            orchestrator.handle_trigger_down()
        else:
            window.set_status("Processing...", "#fab387")  # orange
            result = orchestrator.handle_trigger_up()
            if result:
                window.append_text(result)
            window.set_status("Ready")

    mic.on_trigger = handle_mic_event

    if mic.start():
        logger.info("Medical microphone detected and initialized.")
    else:
        logger.warning("No medical microphone found. Keyboard fallbacks active.")

    logger.info("Application ready.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
