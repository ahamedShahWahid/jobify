"""FastAPI service settings, sourced from environment variables.

Settings are validated at startup; the app refuses to boot on invalid input.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "dev", "staging", "prod"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogFormat = Literal["text", "json"]


_DEFAULT_ALLOWED_RESUME_CONTENT_TYPES = [
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]


class Settings(BaseSettings):
    """Service-wide configuration.

    Backed by environment variables prefixed with ``JOBIFY_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="JOBIFY_",
        env_file=None,  # loaded explicitly via uv run --env-file in dev
        case_sensitive=False,
        extra="ignore",
    )

    env: Environment
    service_name: str
    log_level: LogLevel = "INFO"
    log_format: LogFormat = "text"
    db_url: str = Field(..., description="SQLAlchemy DSN; must use postgresql+asyncpg driver.")
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    db_pool_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    db_pool_recycle_seconds: int = Field(default=1800, ge=60, le=86400)
    db_command_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    storage_root: Path = Field(
        default=Path("var/uploads"),
        description=(
            "Filesystem root for LocalFileStorage." " Relative paths resolve against the API's CWD."
        ),
    )
    storage_backend: Literal["local", "s3"] = Field(
        default="local",
        description="Storage adapter: local filesystem or S3-compatible object storage.",
    )
    s3_bucket: str | None = Field(default=None, description="Required for storage_backend=s3.")
    s3_prefix: str = Field(default="", description="Optional object-key prefix within the bucket.")
    aws_region: str | None = Field(default=None, description="AWS region for S3 and SES.")
    aws_endpoint_url: str | None = Field(
        default=None,
        description="Optional S3-compatible endpoint override (for example LocalStack or MinIO).",
    )
    provider_connect_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    provider_read_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    max_upload_bytes: int = Field(
        default=10 * 1024 * 1024,
        description="Max bytes accepted for an uploaded file (per request).",
    )
    allowed_resume_content_types: list[str] | str = Field(
        default_factory=lambda: list(_DEFAULT_ALLOWED_RESUME_CONTENT_TYPES),
        description="Whitelist of Content-Type values accepted by the resume upload route.",
    )

    # --- Auth / JWT ---
    jwt_secret: str = Field(..., description="HS256 signing secret. Must be at least 32 bytes.")
    jwt_access_ttl_seconds: int = Field(
        default=600,
        gt=0,
        description="Access token lifetime in seconds.",
    )
    jwt_refresh_ttl_seconds: int = Field(
        default=2592000,
        gt=0,
        description="Refresh token lifetime in seconds (default 30 days).",
    )

    # --- Google OAuth ---
    google_oauth_client_ids: list[str] | str = Field(
        ...,
        description=(
            "CSV of accepted Google OAuth Client IDs (one per platform: web/iOS/Android)."
            " An ID token whose `aud` matches any of these is accepted."
        ),
    )
    google_jwks_url: str = Field(
        default="https://www.googleapis.com/oauth2/v3/certs",
        description="Override for tests + offline dev.",
    )
    google_jwks_cache_ttl_seconds: int = Field(
        default=3600,
        gt=0,
        description="In-process JWKS cache lifetime in seconds.",
    )

    # --- Auth policy ---
    auth_require_email_verified: bool = Field(
        default=False,
        description=(
            "When true, reject Google sign-ins with email_verified=false."
            " Off by default; flippable via env."
        ),
    )
    auth_google_rate_limit_per_minute: int = Field(default=10, ge=1, le=1000)
    auth_refresh_rate_limit_per_minute: int = Field(default=30, ge=1, le=1000)

    # --- Employer team management ---
    employer_invite_ttl_days: int = Field(
        default=14,
        ge=1,
        le=365,
        alias="JOBIFY_EMPLOYER_INVITE_TTL_DAYS",
        description="Days a pending employer invite stays valid before lazy-expiring.",
    )

    # --- CORS ---
    cors_allow_origins: list[str] | str = Field(
        default_factory=lambda: ["http://localhost:8080"],
        description=(
            "CSV of browser origins allowed to call the API (the Flutter web dev"
            " server). Mobile clients send no Origin header, so this only gates web."
        ),
    )
    metrics_bearer_token: SecretStr | None = Field(
        default=None,
        description="Bearer token required by /metrics. Mandatory in staging/prod.",
    )

    # --- Shared Redis dependency (rate limiting + readiness) ---
    redis_url: str = Field(
        ...,
        description="Redis connection string used by API rate limiting and readiness.",
    )

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, v: object) -> object:
        return v.upper() if isinstance(v, str) else v

    @field_validator("log_format", mode="before")
    @classmethod
    def _lower_log_format(cls, v: object) -> object:
        return v.lower() if isinstance(v, str) else v

    @field_validator("db_url")
    @classmethod
    def _enforce_async_driver(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError("db_url must use the postgresql+asyncpg:// driver")
        return v

    @field_validator("redis_url")
    @classmethod
    def _enforce_redis_url(cls, v: str) -> str:
        from urllib.parse import urlparse

        if not (v.startswith("redis://") or v.startswith("rediss://")):
            raise ValueError("redis_url must start with redis:// or rediss://")
        if not urlparse(v).hostname:
            raise ValueError("redis_url must include a hostname (e.g. redis://localhost:6379/0)")
        return v

    @field_validator("allowed_resume_content_types", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        """Parse comma-separated env strings into list[str].

        Pydantic-settings defaults to JSON parsing for list fields, which
        would force users to write JOBIFY_ALLOWED_RESUME_CONTENT_TYPES='["a","b"]'.
        A CSV split keeps the env-var format ergonomic.
        """
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @field_validator("jwt_secret")
    @classmethod
    def _enforce_jwt_secret_length(cls, v: str) -> str:
        if len(v.encode("utf-8")) < 32:
            raise ValueError(
                "jwt_secret must be at least 32 bytes (use a cryptographically random secret)"
            )
        return v

    @model_validator(mode="after")
    def _validate_external_adapters(self) -> Settings:
        if self.storage_backend == "s3" and not self.s3_bucket:
            raise ValueError("s3_bucket is required when storage_backend='s3'")
        if self.env in ("staging", "prod") and self.metrics_bearer_token is None:
            raise ValueError("metrics_bearer_token is required in staging/prod")
        return self

    @field_validator("google_oauth_client_ids", mode="before")
    @classmethod
    def _split_google_client_ids(cls, v: object) -> object:
        """Same CSV-parsing behavior as allowed_resume_content_types."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, v: object) -> object:
        """Same CSV-parsing behavior as allowed_resume_content_types."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @field_validator("google_oauth_client_ids")
    @classmethod
    def _enforce_google_client_id_suffix(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("google_oauth_client_ids must contain at least one entry")
        bad = [x for x in v if not x.endswith(".apps.googleusercontent.com")]
        if bad:
            raise ValueError(
                "google_oauth_client_ids must end in .apps.googleusercontent.com;"
                f" bad entries: {bad}"
            )
        return v
