"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the application."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str | None = Field(default=None)
    gemini_model: str = Field(default="gemini-3.1-flash-lite")
    database_url: str = Field(default="sqlite:///./python_template_uv.db")
    max_pdf_size_bytes: int = Field(default=10 * 1024 * 1024)
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    """Load and cache settings for the lifetime of the process."""
    return Settings()
