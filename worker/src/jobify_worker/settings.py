"""Worker and Celery-beat configuration only."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from jobify.settings import Environment, LogFormat, LogLevel

_VALID_EMBEDDING_DIMS = frozenset({128, 256, 512, 768, 1024, 1536, 3072})


class WorkerSettings(BaseSettings):
    """Configuration required by Celery workers and beat only."""

    model_config = SettingsConfigDict(
        env_prefix="JOBIFY_",
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    env: Environment
    service_name: str
    log_level: LogLevel = "INFO"
    log_format: LogFormat = "text"
    db_url: str
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    db_pool_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    db_pool_recycle_seconds: int = Field(default=1800, ge=60, le=86400)
    db_command_timeout_seconds: float = Field(default=30.0, gt=0, le=300)

    storage_root: Path = Path("var/uploads")
    storage_backend: Literal["local", "s3"] = "local"
    s3_bucket: str | None = None
    s3_prefix: str = ""
    aws_region: str | None = None
    aws_endpoint_url: str | None = None

    redis_url: str
    celery_task_always_eager: bool = False
    task_soft_time_limit_seconds: int = Field(default=240, ge=10, le=3600)
    task_time_limit_seconds: int = Field(default=300, ge=10, le=7200)

    gemini_api_key: SecretStr | None = None
    embedding_model: str = "gemini-embedding-2"
    embedding_dim: int = 1536
    match_surface_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    match_vector_weight: float = Field(default=0.6, ge=0.0, le=1.0)
    match_explainer: Literal["templated", "llm"] = "llm"
    match_explainer_model: str = "gemini-2.5-flash"
    score_batch_size: int = Field(default=100, ge=1, le=1000)

    email_channel: Literal["logging", "ses"] = "logging"
    email_from_address: str | None = None
    notify_batch_size: int = Field(default=50, ge=1, le=1000)
    notify_sweep_interval_seconds: int = Field(default=60, ge=5, le=3600)
    notify_lease_seconds: int = Field(default=300, ge=10, le=3600)
    notify_max_attempts: int = Field(default=5, ge=1, le=100)
    outbox_batch_size: int = Field(default=100, ge=1, le=1000)
    outbox_sweep_interval_seconds: int = Field(default=5, ge=1, le=300)
    outbox_lease_seconds: int = Field(default=300, ge=10, le=3600)
    outbox_max_attempts: int = Field(default=10, ge=1, le=100)

    provider_connect_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    provider_read_timeout_seconds: float = Field(default=30.0, gt=0, le=300)

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("log_format", mode="before")
    @classmethod
    def _lower_log_format(cls, value: object) -> object:
        return value.lower() if isinstance(value, str) else value

    @field_validator("db_url")
    @classmethod
    def _async_driver(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("db_url must use the postgresql+asyncpg:// driver")
        return value

    @field_validator("redis_url")
    @classmethod
    def _redis_url(cls, value: str) -> str:
        from urllib.parse import urlparse

        if not (value.startswith("redis://") or value.startswith("rediss://")):
            raise ValueError("redis_url must start with redis:// or rediss://")
        if not urlparse(value).hostname:
            raise ValueError("redis_url must include a hostname")
        return value

    @field_validator("embedding_dim")
    @classmethod
    def _embedding_dim(cls, value: int) -> int:
        if value not in _VALID_EMBEDDING_DIMS:
            raise ValueError(f"embedding_dim must be one of {sorted(_VALID_EMBEDDING_DIMS)}")
        return value

    @model_validator(mode="after")
    def _external_adapters(self) -> WorkerSettings:
        if self.storage_backend == "s3" and not self.s3_bucket:
            raise ValueError("s3_bucket is required when storage_backend='s3'")
        if self.email_channel == "ses" and not self.email_from_address:
            raise ValueError("email_from_address is required when email_channel='ses'")
        if self.task_time_limit_seconds <= self.task_soft_time_limit_seconds:
            raise ValueError("task_time_limit_seconds must exceed task_soft_time_limit_seconds")
        if self.notify_lease_seconds < self.provider_read_timeout_seconds:
            raise ValueError("notify_lease_seconds must cover provider_read_timeout_seconds")
        return self
