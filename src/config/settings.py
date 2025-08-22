"""
Configuration settings for the application.
"""

import os

from dotenv import load_dotenv

from src.exceptions import ConfigurationError

# Load environment variables from .env file
_ = load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        self.openai_api_key: str = self._get_required_env("OPENAI_API_KEY")
        self.openai_model: str = self._get_env("OPENAI_MODEL", "gpt-4o-mini")
        self.openai_api_base: str = self._get_env(
            "OPENAI_API_BASE", "https://api.openai.com/v1"
        )

    def _get_required_env(self, key: str) -> str:
        """Get a required environment variable, raise error if missing."""
        value = os.getenv(key)
        if not value:
            raise ConfigurationError(f"Required environment variable {key} is not set")
        return value

    def _get_env(self, key: str, default: str) -> str:
        """Get an environment variable with a default value."""
        return os.getenv(key, default)


# Global settings instance
settings = Settings()
