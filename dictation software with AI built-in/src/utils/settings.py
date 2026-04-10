import os


class Settings:
    """
    Application settings loaded from environment variables with safe defaults.
    Instantiate a fresh Settings() to pick up the current environment.
    """
    def __init__(self):
        self.whisper_url: str = os.getenv(
            "WHISPER_URL", "http://localhost:8000/transcribe"
        )
        self.llm_url: str = os.getenv(
            "LLM_URL", "http://localhost:8001/v1/completions"
        )
        # Accept hex (0x0911) or decimal (2321) strings
        self.speechmike_vid: int = int(
            os.getenv("SPEECHMIKE_VID", "0x0911"), 0
        )
        self.speechmike_pid: int = int(
            os.getenv("SPEECHMIKE_PID", "0x0c1c"), 0
        )


# Module-level singleton — override by constructing Settings() directly in tests
settings = Settings()
