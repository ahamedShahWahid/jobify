"""Application settings, sourced from environment variables.

Settings are validated at startup; the app refuses to boot on invalid input.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "dev", "staging", "prod"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogFormat = Literal["text", "json"]


_VALID_EMBEDDING_DIMS = frozenset({128, 256, 512, 768, 1024, 1536, 3072})

_DEFAULT_ALLOWED_RESUME_CONTENT_TYPES = [
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]


class Settings(BaseSettings):
    """Service-wide configuration.

    Backed by environment variables prefixed with ``KPA_``.
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
    db_url: str = Field(..., description="SQLAlchemy DSN; must use postgresql+asyncpg driver.")
    storage_root: Path = Field(
        default=Path("var/uploads"),
        description=(
            "Filesystem root for LocalFileStorage." " Relative paths resolve against the API's CWD."
        ),
    )
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

    # --- Embedding worker (Gemini) ---
    gemini_api_key: SecretStr = Field(
        ..., description="Gemini Developer API key for the embedding worker."
    )
    embedding_model: str = Field(
        default="gemini-embedding-2",
        description="Embedding model identifier.",
    )
    embedding_dim: int = Field(
        default=1536,
        description=(
            "Matryoshka output dimension. Must be in"
            f" {sorted(_VALID_EMBEDDING_DIMS)} and match the Vector(N) in the migration."
        ),
    )

    # --- Scoring ---
    match_surface_threshold: float = Field(
        default=0.55,
        ge=0.0,
        le=1.0,
        alias="KPA_MATCH_SURFACE_THRESHOLD",
        description="Total score >= this value marks a match as surfaced (visible in the feed).",
    )
    match_vector_weight: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        alias="KPA_MATCH_VECTOR_WEIGHT",
        description="Weight on the vector score component. Structured weight is 1 - this.",
    )
    match_explainer: str = Field(
        default="llm",
        alias="KPA_MATCH_EXPLAINER",
        description=(
            "Match-explanation generator: 'llm' (Gemini, default) or 'templated' "
            "(deterministic fallback). The LLM impl falls back to templated on any "
            "Gemini error so scoring is never failed by an explanation outage."
        ),
    )
    match_explainer_model: str = Field(
        default="gemini-2.5-flash",
        alias="KPA_MATCH_EXPLAINER_MODEL",
        description="Gemini text-generation model used when match_explainer='llm'.",
    )

    # --- Notifications ---
    email_channel: str = Field(
        default="logging",
        alias="KPA_EMAIL_CHANNEL",
        description="Email channel backend. logging = stub (dev/MVP); ses = real AWS SES (prod).",
    )
    notify_batch_size: int = Field(
        default=50,
        ge=1,
        le=1000,
        alias="KPA_NOTIFY_BATCH_SIZE",
        description="Max notifications the sweeper claims in one pass.",
    )

    # --- CORS ---
    cors_allow_origins: list[str] | str = Field(
        default_factory=lambda: ["http://localhost:8080"],
        description=(
            "CSV of browser origins allowed to call the API (the Flutter web dev"
            " server). Mobile clients send no Origin header, so this only gates web."
        ),
    )

    # --- Background workers (Celery + Redis) ---
    redis_url: str = Field(
        ...,
        description="Redis connection string. Used by Celery broker + result backend.",
    )
    celery_task_always_eager: bool = Field(
        default=False,
        description=(
            "When true, Celery tasks execute synchronously in the calling process"
            " instead of being dispatched to the broker. Used by tests; never in prod."
        ),
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
        would force users to write KPA_ALLOWED_RESUME_CONTENT_TYPES='["a","b"]'.
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

    @field_validator("embedding_dim")
    @classmethod
    def _enforce_valid_embedding_dim(cls, v: int) -> int:
        if v not in _VALID_EMBEDDING_DIMS:
            raise ValueError(
                f"embedding_dim must be one of {sorted(_VALID_EMBEDDING_DIMS)}, got {v}"
            )
        return v

    @field_validator("email_channel")
    @classmethod
    def _enforce_valid_email_channel(cls, v: str) -> str:
        if v not in ("logging", "ses"):
            raise ValueError(f"email_channel must be 'logging' or 'ses', got {v!r}")
        return v

    @field_validator("match_explainer")
    @classmethod
    def _enforce_valid_match_explainer(cls, v: str) -> str:
        if v not in ("templated", "llm"):
            raise ValueError(f"match_explainer must be 'templated' or 'llm', got {v!r}")
        return v

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
