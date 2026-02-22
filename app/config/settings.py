# app/config/settings.py

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "ai-risk-engine"
    environment: Literal["dev", "test", "prod"] = "dev"
    debug: bool = False
    version: str = "0.1.0"

    # --- Security ---
    jwt_secret: str = Field(..., min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    # --- Database ---
    database_url: str

    # --- Redis ---
    redis_url: str

    # --- Messaging ---
    rabbitmq_url: str

    # --- Observability ---
    enable_metrics: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()


# Singleton for direct import (e.g. in infrastructure clients)
settings = get_settings()
