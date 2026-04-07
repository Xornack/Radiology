import sys
from PyQt6.QtWidgets import QApplication
from loguru import logger

# Import modular components
from src.ui.main_window import MainWindow
from src.hardware.recorder import AudioRecorder
from src.hardware.mic_listener import MicListener
from src.ai.whisper_client import WhisperClient
from src.core.orchestrator import DictationOrchestrator
from src.engine import wedge
from src.utils.profiler import LatencyTimer

def main():
    logger.info("Initializing Local AI Radiology Dictation Platform...")
    
    app = QApplication(sys.argv)
    
    # 1. Initialize Components
    # Note: URLs and HID IDs would move to a config/env file in production
    whisper = WhisperClient(url="http://localhost:8000/transcribe")
    recorder = AudioRecorder()
    profiler = LatencyTimer()
    
    # 2. Setup Orchestrator
    orchestrator = DictationOrchestrator(
        recorder=recorder,
        whisper_client=whisper,
        wedge=wedge,
        profiler=profiler
    )
    
    # 3. Setup UI
    window = MainWindow()
    window.show()
    
    # 4. Setup Hardware Listener (SpeechMike Example VID/PID)
    # Philips SpeechMike: 0x0911 / 0x0c1c (Example)
    mic = MicListener(vendor_id=0x0911, product_id=0x0c1c)
    
    # Connect HID events to Orchestrator
    # Note: Real hardware needs a polling thread, but logic is wired here
    def handle_mic_event(pressed):
        if pressed:
            orchestrator.handle_trigger_down()
        else:
            orchestrator.handle_trigger_up()
            
    mic.on_trigger = handle_mic_event
    
    if mic.start():
        logger.info("Medical Microphone detected and initialized.")
    else:
        logger.warning("No Medical Microphone found. Keyboard fallbacks active.")

    logger.info("Application Ready.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
