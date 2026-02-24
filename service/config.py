"""
Centralised configuration loaded from environment variables.

All settings live here — never scattered across modules.
Using pydantic-settings gives us type validation and .env file support for free.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    upstream_url: str = "http://localhost:9000"
    sync_interval_seconds: int = 60
    db_path: str = "/data/alerts.db"
    log_level: str = "INFO"
    default_lookback_hours: int = 24

    class Config:
        env_file = ".env"


# Single shared instance — import this everywhere
settings = Settings()
