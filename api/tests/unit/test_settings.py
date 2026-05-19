"""Tests for the Settings module."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from kpa.settings import Settings


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("KPA_LOG_FORMAT", "text")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa")
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("KPA_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")

    settings = Settings()

    assert settings.env == "local"
    assert settings.log_level == "DEBUG"
    assert settings.log_format == "text"
    assert settings.service_name == "kpa-api"
    assert str(settings.db_url) == "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa"


def test_settings_rejects_unknown_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_LOG_LEVEL", "VERBOSE")  # invalid
    monkeypatch.setenv("KPA_LOG_FORMAT", "text")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_rejects_unknown_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "uat")  # invalid
    monkeypatch.setenv("KPA_LOG_LEVEL", "INFO")
    monkeypatch.setenv("KPA_LOG_FORMAT", "text")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_defaults_when_optional_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    # Required vars only; optional vars take defaults.
    for k in ("KPA_LOG_LEVEL", "KPA_LOG_FORMAT"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa")
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("KPA_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")

    settings = Settings()

    assert settings.log_level == "INFO"
    assert settings.log_format == "text"


def test_settings_raises_when_required_vars_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KPA_ENV", raising=False)
    monkeypatch.delenv("KPA_SERVICE_NAME", raising=False)
    monkeypatch.delenv("KPA_LOG_LEVEL", raising=False)
    monkeypatch.delenv("KPA_LOG_FORMAT", raising=False)
    monkeypatch.delenv("KPA_DB_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_normalizes_log_level_case(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_LOG_LEVEL", "debug")  # lowercase
    monkeypatch.setenv("KPA_LOG_FORMAT", "JSON")  # uppercase
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa")
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("KPA_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")

    settings = Settings()

    assert settings.log_level == "DEBUG"
    assert settings.log_format == "json"


def test_settings_loads_db_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa")
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("KPA_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")

    settings = Settings()

    assert str(settings.db_url) == "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa"


def test_settings_rejects_missing_db_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.delenv("KPA_DB_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_rejects_db_url_with_wrong_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    # Sync driver — must be rejected since the runtime is async-only.
    monkeypatch.setenv("KPA_DB_URL", "postgresql://kpa:kpa@localhost:5432/kpa")

    with pytest.raises(ValidationError):
        Settings()


# ---------------------------------------------------------------------------
# Auth / JWT + Google OAuth settings
# ---------------------------------------------------------------------------


def _set_minimum_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the minimum env vars required by Settings to construct successfully."""
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 32)
    monkeypatch.setenv(
        "KPA_GOOGLE_OAUTH_CLIENT_IDS",
        "abc.apps.googleusercontent.com",
    )


def test_jwt_secret_rejects_short_value(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("KPA_JWT_SECRET", "x" * 31)  # 31 bytes — one short
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
    monkeypatch.setenv("KPA_JWT_ACCESS_TTL_SECONDS", "0")
    with pytest.raises(ValidationError):
        Settings()


def test_google_oauth_client_ids_parses_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv(
        "KPA_GOOGLE_OAUTH_CLIENT_IDS",
        "web.apps.googleusercontent.com , ios.apps.googleusercontent.com",
    )
    s = Settings()
    assert s.google_oauth_client_ids == [
        "web.apps.googleusercontent.com",
        "ios.apps.googleusercontent.com",
    ]


def test_google_oauth_client_ids_rejects_bad_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("KPA_GOOGLE_OAUTH_CLIENT_IDS", "notagoogleclient.example.com")
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
    monkeypatch.delenv("KPA_STORAGE_ROOT", raising=False)

    settings = Settings()

    assert settings.storage_root == Path("var/uploads")


def test_settings_storage_root_honors_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa")
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("KPA_STORAGE_ROOT", str(tmp_path))

    settings = Settings()

    assert settings.storage_root == tmp_path


def test_settings_max_upload_bytes_defaults_to_10mb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa")
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
    _set_minimum_env(monkeypatch)
    monkeypatch.delenv("KPA_MAX_UPLOAD_BYTES", raising=False)

    settings = Settings()

    assert settings.max_upload_bytes == 10 * 1024 * 1024


def test_settings_allowed_resume_content_types_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa")
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
    _set_minimum_env(monkeypatch)
    monkeypatch.delenv("KPA_ALLOWED_RESUME_CONTENT_TYPES", raising=False)

    settings = Settings()

    assert settings.allowed_resume_content_types == [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]


def test_settings_allowed_resume_content_types_parses_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pydantic settings parses comma-separated strings into list[str] for env-var input."""
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa")
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("KPA_ALLOWED_RESUME_CONTENT_TYPES", "application/pdf,text/plain")

    settings = Settings()

    assert settings.allowed_resume_content_types == ["application/pdf", "text/plain"]


# ---------------------------------------------------------------------------
# Background workers (Redis + Celery) settings
# ---------------------------------------------------------------------------


def test_redis_url_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.delenv("KPA_REDIS_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_redis_url_accepts_redis_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")

    s = Settings()
    assert s.redis_url == "redis://localhost:6379/0"


def test_redis_url_accepts_rediss_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("KPA_REDIS_URL", "rediss://user:pw@elasticache:6380/0")

    s = Settings()
    assert s.redis_url.startswith("rediss://")


def test_redis_url_rejects_non_redis_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("KPA_REDIS_URL", "http://localhost:6379")

    with pytest.raises(ValidationError, match="redis://"):
        Settings()


def test_redis_url_rejects_missing_hostname(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("KPA_REDIS_URL", "redis://")  # scheme present, no host

    with pytest.raises(ValidationError, match="hostname"):
        Settings()


def test_celery_task_always_eager_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")

    s = Settings()
    assert s.celery_task_always_eager is False
