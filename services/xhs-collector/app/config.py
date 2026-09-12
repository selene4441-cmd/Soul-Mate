from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, overridable via environment variables or a .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    tikhub_api_key: str = ""
    tikhub_base_url: str = "https://api.tikhub.io"
    database_url: str = "sqlite:///./xhs_leads.db"
    request_interval_seconds: float = 0.3
    auto_create_db: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()