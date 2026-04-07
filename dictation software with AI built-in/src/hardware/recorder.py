import sounddevice as sd
import numpy as np

class AudioRecorder:
    """
    Captures mono audio into an internal buffer.
    Designed for 16kHz audio as required by Whisper.
    """
    def __init__(self, sample_rate=16000, channels=1):
        self.sample_rate = sample_rate
        self.channels = channels
        self._buffer = []
        self._stream = None

    def _audio_callback(self, indata, frames, time, status):
        """
        Callback called by sounddevice for each audio block.
        """
        if status:
            pass
        # indata is a numpy array of shape (frames, channels)
        # We flatten it to a 1D list/array for simplicity in the MVP
        self._buffer.extend(indata.copy().flatten())

    def start(self):
        """
        Starts the audio input stream.
        """
        self._buffer = [] # Clear buffer on start
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            callback=self._audio_callback,
            dtype='float32'
        )
        self._stream.start()

    def stop(self):
        """
        Stops the audio input stream.
        """
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def get_buffer(self) -> np.ndarray:
        """
        Returns the captured audio as a numpy array.
        """
        return np.array(self._buffer, dtype='float32')
