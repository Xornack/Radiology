import requests
from loguru import logger


class WhisperClient:
    """
    Client for interacting with a local Whisper STT microservice.
    """
    def __init__(self, url: str):
        self.url = url

    def transcribe(self, audio_bytes: bytes) -> str:
        """
        Sends WAV audio bytes to the Whisper service and returns transcribed text.
        Returns an empty string on any failure so the pipeline degrades gracefully.
        """
        try:
            files = {'file': ('audio.wav', audio_bytes, 'audio/wav')}
            response = requests.post(self.url, files=files, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return data.get("text", "")

            logger.warning(f"Whisper service returned HTTP {response.status_code}")
            return ""
        except requests.exceptions.Timeout:
            logger.error("Whisper service timed out after 10s")
            return ""
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return ""
