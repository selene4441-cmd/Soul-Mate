from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "同频 API"
    environment: Literal["development", "test", "staging", "production"] = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./tongpin.db"
    redis_url: str = "redis://127.0.0.1:6379/0"
    session_cookie_name: str = "tongpin_session"
    csrf_cookie_name: str = "tongpin_csrf"
    session_ttl_days: int = 14
    cookie_secure: bool = False
    auto_create_db: bool = True
    seed_demo_data: bool = True
    rate_limit_enabled: bool = True
    model_version: str = "rules-v0.1"
    policy_version: str = "cold-start-v0.1"
    consent_version: str = "2026-09-12"
    app_origin: str = "http://localhost:3000"
    max_claim_confidence_age_days: int = 90
    claim_retention_days: int = Field(default=365, ge=1)
    raw_document_retention_days: int = Field(default=180, ge=1)
    connection_request_ttl_days: int = Field(default=7, ge=1, le=30)
    connection_request_cooldown_days: int = Field(default=30, ge=0, le=365)
    outbox_worker_id: str = "api"
    realtime_broker_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
