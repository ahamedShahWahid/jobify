"""Tests for the Settings module."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from jobify_api.settings import Settings
from jobify_worker.settings import WorkerSettings


def test_worker_settings_do_not_require_api_secrets() -> None:
    settings = WorkerSettings(
        env="local",
        service_name="jobify-worker",
        db_url="postgresql+asyncpg://user:pass@localhost/jobify",
        redis_url="redis://localhost:6379/0",
    )
    assert settings.service_name == "jobify-worker"
    assert not hasattr(settings, "jwt_secret")
    assert not hasattr(settings, "google_oauth_client_ids")


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("JOBIFY_LOG_FORMAT", "text")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://jobify:jobify@localhost:5432/jobify")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JOBIFY_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")

    settings = Settings()

    assert settings.env == "local"
    assert settings.log_level == "DEBUG"
    assert settings.log_format == "text"
    assert settings.service_name == "jobify-api"
    assert str(settings.db_url) == "postgresql+asyncpg://jobify:jobify@localhost:5432/jobify"


def test_settings_rejects_unknown_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_LOG_LEVEL", "VERBOSE")  # invalid
    monkeypatch.setenv("JOBIFY_LOG_FORMAT", "text")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://jobify:jobify@localhost:5432/jobify")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_rejects_unknown_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "uat")  # invalid
    monkeypatch.setenv("JOBIFY_LOG_LEVEL", "INFO")
    monkeypatch.setenv("JOBIFY_LOG_FORMAT", "text")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://jobify:jobify@localhost:5432/jobify")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_defaults_when_optional_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    # Required vars only; optional vars take defaults.
    for k in ("JOBIFY_LOG_LEVEL", "JOBIFY_LOG_FORMAT"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://jobify:jobify@localhost:5432/jobify")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JOBIFY_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")

    settings = Settings()

    assert settings.log_level == "INFO"
    assert settings.log_format == "text"


def test_settings_raises_when_required_vars_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JOBIFY_ENV", raising=False)
    monkeypatch.delenv("JOBIFY_SERVICE_NAME", raising=False)
    monkeypatch.delenv("JOBIFY_LOG_LEVEL", raising=False)
    monkeypatch.delenv("JOBIFY_LOG_FORMAT", raising=False)
    monkeypatch.delenv("JOBIFY_DB_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_normalizes_log_level_case(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_LOG_LEVEL", "debug")  # lowercase
    monkeypatch.setenv("JOBIFY_LOG_FORMAT", "JSON")  # uppercase
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://jobify:jobify@localhost:5432/jobify")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JOBIFY_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")

    settings = Settings()

    assert settings.log_level == "DEBUG"
    assert settings.log_format == "json"


def test_settings_loads_db_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://jobify:jobify@localhost:5432/jobify")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JOBIFY_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")

    settings = Settings()

    assert str(settings.db_url) == "postgresql+asyncpg://jobify:jobify@localhost:5432/jobify"


def test_settings_rejects_missing_db_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.delenv("JOBIFY_DB_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_rejects_db_url_with_wrong_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    # Sync driver — must be rejected since the runtime is async-only.
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql://jobify:jobify@localhost:5432/jobify")

    with pytest.raises(ValidationError):
        Settings()


# ---------------------------------------------------------------------------
# Auth / JWT + Google OAuth settings
# ---------------------------------------------------------------------------


def _set_minimum_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the minimum env vars required by Settings to construct successfully."""
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JOBIFY_GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv(
        "JOBIFY_GOOGLE_OAUTH_CLIENT_IDS",
        "abc.apps.googleusercontent.com",
    )


def test_jwt_secret_rejects_short_value(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 31)  # 31 bytes — one short
    with pytest.raises(ValidationError, match="jwt_secret must be at least 32"):
        Settings()


def test_jwt_secret_accepts_32_byte_value(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    s = Settings()
    assert s.jwt_secret == "x" * 32


def test_jwt_ttl_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    s = Settings()
    assert s.jwt_access_ttl_seconds == 600
    assert s.jwt_refresh_ttl_seconds == 2592000


def test_jwt_ttl_rejects_non_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("JOBIFY_JWT_ACCESS_TTL_SECONDS", "0")
    with pytest.raises(ValidationError):
        Settings()


def test_google_oauth_client_ids_parses_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv(
        "JOBIFY_GOOGLE_OAUTH_CLIENT_IDS",
        "web.apps.googleusercontent.com , ios.apps.googleusercontent.com",
    )
    s = Settings()
    assert s.google_oauth_client_ids == [
        "web.apps.googleusercontent.com",
        "ios.apps.googleusercontent.com",
    ]


def test_google_oauth_client_ids_rejects_bad_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("JOBIFY_GOOGLE_OAUTH_CLIENT_IDS", "notagoogleclient.example.com")
    with pytest.raises(ValidationError, match="apps.googleusercontent.com"):
        Settings()


def test_google_jwks_url_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    s = Settings()
    assert s.google_jwks_url == "https://www.googleapis.com/oauth2/v3/certs"


def test_auth_require_email_verified_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    s = Settings()
    assert s.auth_require_email_verified is False


# ---------------------------------------------------------------------------
# Resume upload settings (from P1.0)
# ---------------------------------------------------------------------------


def test_settings_storage_root_defaults_to_var_uploads(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.delenv("JOBIFY_STORAGE_ROOT", raising=False)

    settings = Settings()

    assert settings.storage_root == Path("var/uploads")


def test_settings_storage_root_honors_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://jobify:jobify@localhost:5432/jobify")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("JOBIFY_STORAGE_ROOT", str(tmp_path))

    settings = Settings()

    assert settings.storage_root == tmp_path


def test_settings_max_upload_bytes_defaults_to_10mb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://jobify:jobify@localhost:5432/jobify")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    _set_minimum_env(monkeypatch)
    monkeypatch.delenv("JOBIFY_MAX_UPLOAD_BYTES", raising=False)

    settings = Settings()

    assert settings.max_upload_bytes == 10 * 1024 * 1024


def test_settings_allowed_resume_content_types_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://jobify:jobify@localhost:5432/jobify")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    _set_minimum_env(monkeypatch)
    monkeypatch.delenv("JOBIFY_ALLOWED_RESUME_CONTENT_TYPES", raising=False)

    settings = Settings()

    assert settings.allowed_resume_content_types == [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]


def test_settings_allowed_resume_content_types_parses_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pydantic settings parses comma-separated strings into list[str] for env-var input."""
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://jobify:jobify@localhost:5432/jobify")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("JOBIFY_ALLOWED_RESUME_CONTENT_TYPES", "application/pdf,text/plain")

    settings = Settings()

    assert settings.allowed_resume_content_types == ["application/pdf", "text/plain"]


# ---------------------------------------------------------------------------
# Background workers (Redis + Celery) settings
# ---------------------------------------------------------------------------


def test_redis_url_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.delenv("JOBIFY_REDIS_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_redis_url_accepts_redis_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")

    s = Settings()
    assert s.redis_url == "redis://localhost:6379/0"


def test_redis_url_accepts_rediss_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "rediss://user:pw@elasticache:6380/0")

    s = Settings()
    assert s.redis_url.startswith("rediss://")


def test_redis_url_rejects_non_redis_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "http://localhost:6379")

    with pytest.raises(ValidationError, match="redis://"):
        Settings()


def test_redis_url_rejects_missing_hostname(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://")  # scheme present, no host

    with pytest.raises(ValidationError, match="hostname"):
        Settings()


def test_celery_task_always_eager_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")

    s = WorkerSettings()
    assert s.celery_task_always_eager is False


# ---------------------------------------------------------------------------
# Embedding worker (Gemini) settings
# ---------------------------------------------------------------------------


def test_gemini_api_key_is_optional_at_settings_load(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.delenv("JOBIFY_GEMINI_API_KEY", raising=False)
    s = WorkerSettings()
    assert s.gemini_api_key is None


def test_embedding_model_default_is_gemini_2(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.delenv("JOBIFY_EMBEDDING_MODEL", raising=False)
    s = WorkerSettings()
    assert s.embedding_model == "gemini-embedding-2"


def test_embedding_dim_default_is_1536(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.delenv("JOBIFY_EMBEDDING_DIM", raising=False)
    s = WorkerSettings()
    assert s.embedding_dim == 1536


def test_embedding_dim_rejects_unsupported_value(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("JOBIFY_EMBEDDING_DIM", "999")
    with pytest.raises(ValidationError, match="embedding_dim must be one of"):
        WorkerSettings()


@pytest.mark.parametrize("dim", [128, 256, 512, 768, 1024, 1536, 3072])
def test_embedding_dim_accepts_supported_values(monkeypatch: pytest.MonkeyPatch, dim: int) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("JOBIFY_EMBEDDING_DIM", str(dim))
    s = WorkerSettings()
    assert s.embedding_dim == dim


# ---------------------------------------------------------------------------
# Scoring settings (from P2.2)
# ---------------------------------------------------------------------------


def test_match_surface_threshold_out_of_range_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("JOBIFY_MATCH_SURFACE_THRESHOLD", "1.5")
    with pytest.raises(ValidationError):
        WorkerSettings()


def test_match_vector_weight_out_of_range_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("JOBIFY_MATCH_VECTOR_WEIGHT", "-0.1")
    with pytest.raises(ValidationError):
        WorkerSettings()


def test_match_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    s = WorkerSettings()
    assert s.match_surface_threshold == 0.55
    assert s.match_vector_weight == 0.6
    assert s.score_batch_size == 100


def test_score_batch_size_out_of_range_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("JOBIFY_SCORE_BATCH_SIZE", "0")
    with pytest.raises(ValidationError):
        WorkerSettings()


# ---------------------------------------------------------------------------
# Notifications settings (from P3.1)
# ---------------------------------------------------------------------------


def test_email_channel_default_is_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.delenv("JOBIFY_EMAIL_CHANNEL", raising=False)
    s = WorkerSettings()
    assert s.email_channel == "logging"


def test_email_channel_invalid_value_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("JOBIFY_EMAIL_CHANNEL", "sendgrid")
    with pytest.raises(ValidationError, match="email_channel"):
        WorkerSettings()


def test_notify_batch_size_out_of_range_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("JOBIFY_NOTIFY_BATCH_SIZE", "0")
    with pytest.raises(ValidationError):
        WorkerSettings()


# ---------------------------------------------------------------------------
# Durable outbox settings
# ---------------------------------------------------------------------------


def test_outbox_cleanup_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    settings = WorkerSettings()
    assert settings.outbox_retention_days == 30
    assert settings.outbox_cleanup_batch_size == 1000


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("JOBIFY_OUTBOX_RETENTION_DAYS", "0"),
        ("JOBIFY_OUTBOX_RETENTION_DAYS", "3651"),
        ("JOBIFY_OUTBOX_CLEANUP_BATCH_SIZE", "0"),
        ("JOBIFY_OUTBOX_CLEANUP_BATCH_SIZE", "10001"),
    ],
)
def test_outbox_cleanup_settings_reject_out_of_range_values(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        WorkerSettings()


# ---------------------------------------------------------------------------
# Match-explainer settings (from sub-project G)
# ---------------------------------------------------------------------------


def test_match_explainer_default_is_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.delenv("JOBIFY_MATCH_EXPLAINER", raising=False)
    s = WorkerSettings()
    assert s.match_explainer == "llm"


def test_match_explainer_templated_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("JOBIFY_MATCH_EXPLAINER", "templated")
    s = WorkerSettings()
    assert s.match_explainer == "templated"


def test_match_explainer_invalid_value_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("JOBIFY_MATCH_EXPLAINER", "openai")
    with pytest.raises(ValidationError, match="match_explainer"):
        WorkerSettings()


def test_match_explainer_model_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.delenv("JOBIFY_MATCH_EXPLAINER_MODEL", raising=False)
    s = WorkerSettings()
    assert s.match_explainer_model == "gemini-2.5-flash"


def test_match_explainer_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("JOBIFY_MATCH_EXPLAINER_MODEL", "gemini-2.5-pro")
    s = WorkerSettings()
    assert s.match_explainer_model == "gemini-2.5-pro"


def test_worker_hard_time_limit_must_exceed_soft_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("JOBIFY_TASK_SOFT_TIME_LIMIT_SECONDS", "300")
    monkeypatch.setenv("JOBIFY_TASK_TIME_LIMIT_SECONDS", "300")
    with pytest.raises(ValidationError, match="must exceed"):
        WorkerSettings()


def test_notification_lease_must_cover_provider_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("JOBIFY_NOTIFY_LEASE_SECONDS", "20")
    monkeypatch.setenv("JOBIFY_PROVIDER_READ_TIMEOUT_SECONDS", "30")
    with pytest.raises(ValidationError, match="must cover"):
        WorkerSettings()


def test_notification_lease_includes_connect_read_and_completion_margin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("JOBIFY_NOTIFY_LEASE_SECONDS", "35")
    monkeypatch.setenv("JOBIFY_PROVIDER_CONNECT_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("JOBIFY_PROVIDER_READ_TIMEOUT_SECONDS", "30")
    with pytest.raises(ValidationError, match="connect, read, and completion margin"):
        WorkerSettings()
