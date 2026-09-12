from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite+pysqlite:///./data/soulmate.db"

    openai_base_url: str | None = None
    openai_model: str | None = None
    openai_embedding_model: str | None = None
    openai_api_key: str | None = None


settings = Settings()
