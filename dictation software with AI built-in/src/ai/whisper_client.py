import time
import requests
from loguru import logger


class WhisperClient:
    """
    Client for interacting with a local Whisper STT microservice.
    """
    # HTTP Whisper is fast enough to drive 1.5s streaming ticks.
    supports_streaming: bool = True

    def __init__(self, url: str, max_retries: int = 2, retry_initial_delay: float = 0.5):
        self.url = url
        self.max_retries = max_retries
        self.retry_initial_delay = retry_initial_delay

    def transcribe(self, audio_bytes: bytes) -> str:
        """
        Sends WAV audio bytes to the Whisper service and returns transcribed text.
        Retries on transient failures (timeout, 5xx) with exponential backoff.
        Returns an empty string on permanent failure so the pipeline degrades gracefully.
        """
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                files = {'file': ('audio.wav', audio_bytes, 'audio/wav')}
                response = requests.post(self.url, files=files, timeout=10)

                if response.status_code == 200:
                    return response.json().get("text", "")

                last_error = f"HTTP {response.status_code}"
                # Only retry on transient server errors
                if not (500 <= response.status_code < 600):
                    logger.warning(f"Whisper returned {last_error}; not retrying")
                    return ""
                logger.warning(
                    f"Whisper returned {last_error} (attempt {attempt + 1}/"
                    f"{self.max_retries + 1})"
                )
            except requests.exceptions.ConnectionError as e:
                # Server isn't running / port closed — retrying won't help, fail fast
                logger.error(f"Whisper unreachable at {self.url}: {e}")
                return ""
            except requests.exceptions.Timeout:
                last_error = "timeout"
                logger.warning(
                    f"Whisper timed out (attempt {attempt + 1}/{self.max_retries + 1})"
                )
            except Exception as e:
                last_error = str(e)
                logger.error(
                    f"Whisper request failed (attempt {attempt + 1}/"
                    f"{self.max_retries + 1}): {e}"
                )

            if attempt < self.max_retries:
                time.sleep(self.retry_initial_delay * (2 ** attempt))

        logger.error(
            f"Whisper failed after {self.max_retries + 1} attempts: {last_error}"
        )
        return ""
