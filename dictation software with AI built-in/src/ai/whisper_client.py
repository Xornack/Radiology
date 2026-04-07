import requests

class WhisperClient:
    """
    Client for interacting with a local Whisper STT microservice.
    """
    def __init__(self, url: str):
        self.url = url

    def transcribe(self, audio_bytes: bytes) -> str:
        """
        Sends audio bytes to the Whisper service and returns the transcribed text.
        """
        try:
            # Send audio as a file in a POST request
            files = {'file': ('audio.wav', audio_bytes, 'audio/wav')}
            response = requests.post(self.url, files=files, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("text", "")
            else:
                return ""
        except Exception:
            return ""
