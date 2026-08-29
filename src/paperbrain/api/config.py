from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# src/paperbrain/api/config.py -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]


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
    state_path: str = "data/state.json"
    ui_dist_path: str = "apps/planner-web/dist"
    seed_demo: bool = False

    @property
    def resolved_state_path(self) -> Path | None:
        """Absolute state file path, or None when persistence is disabled."""
        if not self.state_path:
            return None
        return _anchor(self.state_path)

    @property
    def resolved_ui_dist_path(self) -> Path:
        """Absolute path to the built single-page app."""
        return _anchor(self.ui_dist_path)


def _anchor(raw: str) -> Path:
    """Resolve relative config paths against the repo root, not the process CWD."""
    path = Path(raw).expanduser()
    return path if path.is_absolute() else (REPO_ROOT / path)


@lru_cache
def get_settings() -> Settings:
    return Settings()
