"""
Configuration module for Solana Token Guardian Agent.
Loads API keys and settings from .env file.
"""

import os
import warnings
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / ".env")


class Config:
    """Centralised configuration loaded from environment variables."""

    def __init__(self):
        self.helius_api_key: str = self._require("HELIUS_API_KEY")
        self.rugcheck_api_key: str | None = self._optional("RUGCHECK_API_KEY")
        self.output_dir: str = os.getenv("OUTPUT_DIR", "./output")

        # Create output directory if it doesn't exist
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        if not self.rugcheck_api_key:
            warnings.warn(
                "RUGCHECK_API_KEY not set. RugCheck data will use unauthenticated "
                "public endpoints (rate limits may apply).",
                UserWarning,
                stacklevel=2,
            )

    @staticmethod
    def _require(key: str) -> str:
        value = os.getenv(key)
        if not value:
            raise EnvironmentError(
                f"Required environment variable '{key}' is not set. "
                f"Copy .env.example to .env and fill in your API keys."
            )
        return value

    @staticmethod
    def _optional(key: str) -> str | None:
        return os.getenv(key) or None


# Module-level convenience accessors (populated lazily so imports don't fail)
def get_config() -> Config:
    """Return a Config instance, raising EnvironmentError if required keys are missing."""
    return Config()
