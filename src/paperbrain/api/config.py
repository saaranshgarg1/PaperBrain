from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PAPERBRAIN_",
        env_file=".env",
        extra="ignore",
    )

    env: str = "local"
    database_url: str = "postgresql+psycopg://paperbrain:paperbrain@localhost:5432/paperbrain"
    log_level: str = "INFO"
    default_time_limit_seconds: int = 30
    allow_provisional_scenarios: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
