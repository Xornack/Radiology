import io
import threading
import wave
import numpy as np
import sounddevice as sd
from loguru import logger


def list_input_devices() -> list[dict]:
    """
    Enumerate audio input devices available on this system.
    Returns a list of dicts with keys: index, name, hostapi_name, channels,
    default_samplerate, is_default.
    """
    try:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
    except Exception as e:
        logger.error(f"Failed to enumerate audio devices: {e}")
        return []

    try:
        default_input_idx = sd.default.device[0]
    except Exception:
        default_input_idx = None

    result = []
    for idx, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) <= 0:
            continue
        hostapi_name = ""
        try:
            hostapi_name = hostapis[dev["hostapi"]]["name"]
        except (IndexError, KeyError, TypeError):
            pass
        result.append({
            "index": idx,
            "name": dev.get("name", f"Device {idx}"),
            "hostapi_name": hostapi_name,
            "channels": dev.get("max_input_channels", 0),
            "default_samplerate": dev.get("default_samplerate", 0),
            "is_default": idx == default_input_idx,
        })
    return result


class AudioRecorder:
    """
    Captures mono audio into an internal buffer.
    Designed for 16kHz audio as required by Whisper.
    """
    def __init__(self, sample_rate: int = 16000, channels: int = 1, device: int | None = None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device   # None = system default input
        self._buffer: list = []
        self._buffer_lock = threading.Lock()
        self._stream = None

    def set_device(self, device: int | None):
        """Change the input device. Takes effect on the next start()."""
        self.device = device

    def _audio_callback(self, indata, frames, time, status):
        """Callback invoked by sounddevice for each audio block."""
        if status:
            logger.warning(f"Audio stream status: {status}")
        flat = indata.copy().flatten()
        with self._buffer_lock:
            self._buffer.extend(flat)

    def start(self):
        """Starts the audio input stream, closing any previous stream first."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._buffer_lock:
            self._buffer = []
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                callback=self._audio_callback,
                dtype='float32',
                device=self.device,
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
        with self._buffer_lock:
            return np.array(self._buffer, dtype='float32')

    def get_wav_bytes(self) -> bytes:
        """
        Returns the captured audio as WAV-format bytes (16-bit PCM, mono, 16kHz).
        This is the format expected by Whisper STT services.
        """
        with self._buffer_lock:
            audio_array = np.array(self._buffer, dtype='float32')

        pcm_float = audio_array * 32767
        clipped = np.clip(pcm_float, -32768, 32767)
        if audio_array.size > 0 and not np.array_equal(clipped, pcm_float):
            logger.warning(
                "Audio clipped during PCM conversion — input levels too high"
            )
        pcm = clipped.astype(np.int16)

        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)          # 16-bit = 2 bytes per sample
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm.tobytes())
        return buf.getvalue()

    def get_sample_count(self) -> int:
        """Current number of captured samples. Lock-safe cheap read."""
        with self._buffer_lock:
            return len(self._buffer)

    def get_wav_bytes_slice(self, start_sample: int, end_sample: int) -> bytes:
        """Encode buffer[start_sample:end_sample] as 16 kHz mono PCM WAV.

        Raises ValueError for reversed or out-of-bounds ranges — silent
        truncation would hide splitter bugs.
        """
        if start_sample < 0 or end_sample < start_sample:
            raise ValueError(
                f"Invalid slice range: [{start_sample}, {end_sample}]"
            )
        with self._buffer_lock:
            buf_len = len(self._buffer)
            if end_sample > buf_len:
                raise ValueError(
                    f"end_sample {end_sample} exceeds buffer length {buf_len}"
                )
            audio_array = np.array(
                self._buffer[start_sample:end_sample], dtype="float32"
            )

        pcm_float = audio_array * 32767
        clipped = np.clip(pcm_float, -32768, 32767)
        pcm = clipped.astype(np.int16)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm.tobytes())
        return buf.getvalue()
