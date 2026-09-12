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

    # Extensions (skills/plugins)
    skills_dir: str = "skills"
    plugins_dir: str = "plugins"
    # Comma-separated skill ids; later skills override earlier ones.
    active_skills: str = ""

    # Auth / Cookies
    session_ttl_seconds: int = 60 * 60 * 24 * 14  # 14 days
    cookie_secure: bool = False
    cookie_samesite: str = "lax"  # "lax" | "strict" | "none"
    session_cookie_name: str = "tongpin_session"
    csrf_cookie_name: str = "tongpin_csrf"


settings = Settings()
