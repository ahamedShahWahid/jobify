"""Application settings, sourced from environment variables.

Settings are validated at startup; the app refuses to boot on invalid input.
"""

from __future__ import annotations

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "dev", "staging", "prod"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogFormat = Literal["text", "json"]


class Settings(BaseSettings):
    """Service-wide configuration.

    Backed by environment variables prefixed with `KPA_`.
    """

    model_config = SettingsConfigDict(
        env_prefix="KPA_",
        env_file=None,  # loaded explicitly via uv run --env-file in dev
        case_sensitive=False,
        extra="ignore",
    )

    env: Environment
    service_name: str
    log_level: LogLevel = "INFO"
    log_format: LogFormat = "text"

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, v: object) -> object:
        return v.upper() if isinstance(v, str) else v

    @field_validator("log_format", mode="before")
    @classmethod
    def _lower_log_format(cls, v: object) -> object:
        return v.lower() if isinstance(v, str) else v
