import io
import wave
import numpy as np
import sounddevice as sd
from loguru import logger


class AudioRecorder:
    """
    Captures mono audio into an internal buffer.
    Designed for 16kHz audio as required by Whisper.
    """
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self._buffer: list = []
        self._stream = None

    def _audio_callback(self, indata, frames, time, status):
        """Callback invoked by sounddevice for each audio block."""
        if status:
            logger.warning(f"Audio stream status: {status}")
        self._buffer.extend(indata.copy().flatten())

    def start(self):
        """Starts the audio input stream, closing any previous stream first."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        self._buffer = []
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                callback=self._audio_callback,
                dtype='float32'
            )
            self._stream.start()
        except Exception as e:
            logger.error(f"Failed to open audio stream: {e}")
            raise

    def stop(self):
        """Stops and closes the audio input stream."""
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def get_buffer(self) -> np.ndarray:
        """Returns the captured audio as a float32 numpy array."""
        return np.array(self._buffer, dtype='float32')

    def get_wav_bytes(self) -> bytes:
        """
        Returns the captured audio as WAV-format bytes (16-bit PCM, mono, 16kHz).
        This is the format expected by Whisper STT services.
        """
        audio_array = np.array(self._buffer, dtype='float32')
        pcm = (audio_array * 32767).clip(-32768, 32767).astype(np.int16)

        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)          # 16-bit = 2 bytes per sample
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm.tobytes())
        return buf.getvalue()
