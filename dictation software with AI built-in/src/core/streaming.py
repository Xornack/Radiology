import threading
from typing import Optional
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from loguru import logger


class StreamingTranscriber(QObject):
    """
    Periodically transcribes the current audio buffer during recording and
    emits partial-text updates on the Qt main thread.

    Each tick is dispatched to a worker thread so the UI stays responsive.
    Ticks are skipped if a previous transcribe is still in flight, which
    prevents the queue from blowing up on long dictations.
    """
    partial_ready = pyqtSignal(str)

    def __init__(
        self,
        recorder,
        whisper_client,
        interval_ms: int = 1500,
        min_audio_seconds: float = 0.5,
        sample_rate: int = 16000,
        parent=None,
    ):
        super().__init__(parent)
        self.recorder = recorder
        self.whisper_client = whisper_client
        self.interval_ms = interval_ms
        self.min_audio_seconds = min_audio_seconds
        self.sample_rate = sample_rate
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._worker: Optional[threading.Thread] = None
        self._in_flight = False
        self._active = False

    def start(self):
        self._active = True
        self._in_flight = False
        self._timer.start(self.interval_ms)

    def stop(self):
        """
        Stops scheduling new ticks. In-flight workers finish on their own but
        their results are discarded because `_active` is False.
        """
        self._active = False
        self._timer.stop()

    def _tick(self):
        if self._in_flight or not self._active:
            return
        try:
            wav_bytes = self.recorder.get_wav_bytes()
        except Exception as e:
            logger.error(f"Streaming tick: could not encode WAV: {e}")
            return
        # 44-byte RIFF header + 2 bytes per 16-bit mono sample
        audio_samples = max(0, len(wav_bytes) - 44) // 2
        if audio_samples < int(self.sample_rate * self.min_audio_seconds):
            return

        self._in_flight = True
        self._worker = threading.Thread(
            target=self._transcribe_worker,
            args=(wav_bytes,),
            daemon=True,
        )
        self._worker.start()

    def _transcribe_worker(self, wav_bytes: bytes):
        try:
            text = self.whisper_client.transcribe(wav_bytes)
            if self._active and text:
                self.partial_ready.emit(text)
        except Exception as e:
            logger.error(f"Streaming transcribe failed: {e}")
        finally:
            self._in_flight = False
