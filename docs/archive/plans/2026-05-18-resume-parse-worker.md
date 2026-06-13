# Resume Parse Worker (Celery + library/regex parser) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the first asynchronous worker — Celery + Redis on Homebrew, library/regex resume parser behind a `ResumeParser` Protocol, dispatched from the upload route, with idempotent retries and polling-based status surfacing.

**Architecture:** A separate `celery worker --pool=solo` process consumes from the `parse` queue. Each sync task body opens its own asyncio loop via `asyncio.run()` and uses a per-worker-process AsyncEngine. The task body splits work into three transactions (load+gate → mark parsing → persist final) so the multi-second extraction never holds a row lock. Parse failures are typed: `ParserError` is permanent (no retry, → `failed`), `TransientParserError` triggers Celery autoretry up to 3× with exponential backoff. The upload route dispatches `parse_resume.delay(...)` after commit; broker outages are logged but don't fail the upload.

**Tech Stack:** Python 3.12, Celery 5.5 with Redis broker, pypdf + pdfminer.six (PDF text extraction with fallback), python-docx (DOCX extraction), Pydantic v2 for the canonical `ParsedResume` schema, structlog for events.

**Spec ref:** `docs/superpowers/specs/2026-05-18-resume-parse-worker-design.md` (approved 2026-05-18).

---

## Branch + base context

- Branch: `feat/p1.1-resume-parse-worker` cut from `origin/feat/p0-db-layer-and-user-model` at SHA `feb672d` (which has P1.0 resume-upload work merged in but not the in-flight auth branch).
- Pre-existing baseline: 8 unit tests + 12 integration tests = 20 tests passing.
- No migration changes — this plan reuses the existing `kpa.resumes` columns (`parse_status`, `parse_error`, `parsed_json`, `updated_at`).
- After this plan: ~35 tests (12 new unit + 3 new integration), one new background process (`celery worker`), one new infra dep (Redis via Homebrew).

## File structure after this plan

```
api/src/kpa/
  workers/                              NEW
    __init__.py
    celery_app.py                       Celery instance + per-worker engine via
                                        worker_process_init signal; get_session_maker()
    tasks/
      __init__.py
      parse.py                          parse_resume sync entry + _parse_resume_async
                                        (3-txn split + idempotency + retry)

  integrations/parser/                  NEW
    __init__.py                         Re-exports
    base.py                             ResumeParser Protocol, ParsedResume,
                                        Experience/Education/CertificationEntry,
                                        ParserError, TransientParserError
    text.py                             extract_text(): pypdf → pdfminer fallback,
                                        python-docx, error classification
    library.py                          LibraryResumeParser — regex + keyword impl
    skills_dict.py                      Curated ~200-entry skill keyword set

  routes/resumes.py                     MODIFY — dispatch parse_resume.delay() after commit
  settings.py                           APPEND — KPA_REDIS_URL,
                                        KPA_CELERY_TASK_ALWAYS_EAGER

  pyproject.toml                        + celery[redis], pypdf, pdfminer.six,
                                        python-docx (runtime); fpdf2 (dev — fixture gen)

  .env.example                          + Background workers section

api/tests/
  unit/
    test_parser_text.py                 NEW — extract_text() across PDF/DOCX paths +
                                        error cases (uses fpdf2 + python-docx fixtures)
    test_parser_library.py              NEW — LibraryResumeParser on canned text
    test_parse_task.py                  NEW — task body with mocked storage + session
    test_settings.py                    APPEND — Redis URL validator + eager flag
  integration/
    test_parse_pipeline.py              NEW — full upload → parse round trip (eager)
    test_dispatch_resilient.py          NEW — broker down ⇒ upload still 201

api/README.md                           APPEND — Redis setup, worker run command,
                                        Auth section unchanged
docs/IMPLEMENTATION_SPEC.md             EDIT §13 + §11.1 — Redis moves P3 → P1
```

---

## Task 1: Add Celery + parser deps + dev-only fpdf2 (test fixtures)

**Files:**
- Modify: `api/pyproject.toml`

Four runtime libraries and one dev-only fixture generator:
- `celery[redis]>=5.5,<6` — task broker; bundles `redis-py`.
- `pypdf>=5,<6` — primary PDF text extractor (fast, modern PDFs).
- `pdfminer.six>=20240706` — fallback PDF extractor (layout-tolerant, slower).
- `python-docx>=1.1,<2` — DOCX extractor.
- `fpdf2>=2.7,<3` — **dev-only**; lets unit tests generate tiny PDF blobs without committing binary fixtures.

- [ ] **Step 1: Edit `api/pyproject.toml`**

In `[project].dependencies`, append (keep alphabetical-by-eye ordering):

```toml
    "celery[redis]>=5.5,<6",
    "pdfminer.six>=20240706",
    "pypdf>=5,<6",
    "python-docx>=1.1,<2",
```

In `[dependency-groups].dev`, append:

```toml
    "fpdf2>=2.7,<3",
```

Final relevant block (preserve everything else exactly):

```toml
dependencies = [
    "alembic>=1.14,<2",
    "anyio>=4,<5",
    "asyncpg>=0.30,<0.31",
    "celery[redis]>=5.5,<6",
    "fastapi>=0.115,<0.116",
    "pdfminer.six>=20240706",
    "pydantic>=2.9,<3",
    "pydantic-settings>=2.5,<3",
    "pypdf>=5,<6",
    "python-docx>=1.1,<2",
    "python-multipart>=0.0.12,<0.1",
    "sqlalchemy[asyncio]>=2.0.36,<2.1",
    "structlog>=24.4,<25",
    "uvicorn[standard]>=0.32,<0.33",
]

[dependency-groups]
dev = [
    "pytest>=8.3,<9",
    "pytest-asyncio>=0.24,<0.25",
    "httpx>=0.27,<0.28",
    "ruff>=0.7,<0.8",
    "mypy>=1.13,<2",
    "fpdf2>=2.7,<3",
]
```

- [ ] **Step 2: Sync deps**

```bash
cd api
uv sync
```

Expected: `uv.lock` updates; `celery`, `kombu`, `redis`, `pypdf`, `pdfminer.six`, `python-docx`, `fpdf2`, `cryptography` (transitive via pdfminer) install. No errors.

- [ ] **Step 3: Verify imports**

```bash
uv run python -c "
import celery, pypdf, pdfminer.high_level, docx, fpdf
print('celery:', celery.__version__)
print('pypdf:', pypdf.__version__)
print('python-docx (docx module):', docx.__version__ if hasattr(docx, '__version__') else 'n/a')
print('fpdf2:', fpdf.FPDF_VERSION)
print('pdfminer.high_level: OK')
"
```

Expected: prints versions, no `ImportError`.

- [ ] **Step 4: Existing tests still green**

```bash
uv run ruff check src/ tests/
uv run mypy
uv run pytest -v
```

All pass (20 baseline tests).

- [ ] **Step 5: Commit**

```bash
git add api/pyproject.toml api/uv.lock
git commit -m "$(cat <<'EOF'
chore(api): add celery + pdf/docx parser deps + fpdf2 (dev)

celery[redis] is the task broker for the parse worker. pypdf is the
primary PDF text extractor; pdfminer.six is the layout-tolerant
fallback. python-docx handles .docx. fpdf2 is dev-only — unit tests
use it to generate tiny PDF blobs in-process so we don't commit
binary fixtures.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Settings — Redis URL + eager-mode flag

**Files:**
- Modify: `api/src/kpa/settings.py`
- Modify: `api/tests/unit/test_settings.py`
- Modify: `api/.env.example`

Two new env vars. `KPA_REDIS_URL` is required (worker can't run without it). `KPA_CELERY_TASK_ALWAYS_EAGER` defaults `false`; tests flip it on.

- [ ] **Step 1: Write the failing tests**

Append to `api/tests/unit/test_settings.py`:

```python
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


def test_celery_task_always_eager_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")

    s = Settings()
    assert s.celery_task_always_eager is False
```

The first import block at the top of `test_settings.py` already has `from pydantic import ValidationError` and `import pytest`. Confirm before adding; don't duplicate.

The 4 pre-existing tests that already construct `Settings()` (test_settings_loads_from_env, test_settings_defaults_when_optional_missing, test_settings_normalizes_log_level_case, test_settings_loads_db_url) need the new required `KPA_REDIS_URL` added to their env setup. Find each call to `Settings()` and add this line **immediately above** it:

```python
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
```

- [ ] **Step 2: Run the new tests, confirm they fail**

```bash
cd api
uv run pytest tests/unit/test_settings.py -v -k "redis_url or celery_task"
```

Expected: 5 tests fail with `AttributeError: 'Settings' object has no attribute 'redis_url'` or pydantic `ValidationError` because the field isn't declared.

- [ ] **Step 3: Implement Settings additions**

Edit `api/src/kpa/settings.py`. Append two new fields inside the `Settings` class, after the existing `allowed_resume_content_types` field:

```python
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
```

Add a validator below the existing `_split_csv` validator:

```python
    @field_validator("redis_url")
    @classmethod
    def _enforce_redis_scheme(cls, v: str) -> str:
        if not (v.startswith("redis://") or v.startswith("rediss://")):
            raise ValueError("redis_url must start with redis:// or rediss://")
        return v
```

- [ ] **Step 4: Update `.env.example`**

Append to `api/.env.example`:

```
# Background workers (Celery + Redis)
KPA_REDIS_URL=redis://localhost:6379/0
KPA_CELERY_TASK_ALWAYS_EAGER=false
```

- [ ] **Step 5: Update integration conftest's `migrated_db` fixture + unit `client` fixture**

The session-scoped `migrated_db` fixture in `api/tests/integration/conftest.py` constructs Settings implicitly. Find the `monkeypatch_session.setenv("KPA_DB_URL", db_url)` line and add directly after it:

```python
    monkeypatch_session.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
```

The integration `client` fixture also calls `create_app()` (which constructs Settings). Find the line `monkeypatch.setenv("KPA_DB_URL", db_url)` in `client` fixture and add directly after it:

```python
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
```

Do the same for the unit `client` fixture in `api/tests/conftest.py`: find the `monkeypatch.setenv("KPA_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")` line and add directly after:

```python
    monkeypatch.setenv("KPA_REDIS_URL", "redis://localhost:6379/0")
```

If `api/tests/unit/test_error_handler.py`, `test_logging.py`, or `test_session.py` construct Settings/create_app, audit them similarly (the auth plan touched the same pattern). Add the `KPA_REDIS_URL` setenv before each Settings construction.

- [ ] **Step 6: Run tests, confirm green**

```bash
uv run pytest -v
```

All pass (20 baseline + 5 new = 25).

- [ ] **Step 7: Lint + types**

```bash
uv run ruff check src/ tests/
uv run mypy
```

All clean.

- [ ] **Step 8: Commit**

```bash
git add api/src/kpa/settings.py api/.env.example \
    api/tests/conftest.py api/tests/integration/conftest.py \
    api/tests/unit/test_settings.py
# add other test files only if you had to edit them in Step 5
git commit -m "$(cat <<'EOF'
feat(api): add KPA_REDIS_URL + KPA_CELERY_TASK_ALWAYS_EAGER settings

KPA_REDIS_URL is required (the parse worker can't run without it).
Validator accepts redis:// or rediss:// so prod TLS swap is config-only.
KPA_CELERY_TASK_ALWAYS_EAGER defaults false; tests flip it on so
.delay() runs the task body inline without a broker.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Parser interface — `ResumeParser` Protocol, `ParsedResume`, errors

**Files:**
- Create: `api/src/kpa/integrations/parser/__init__.py`
- Create: `api/src/kpa/integrations/parser/base.py`
- Create: `api/tests/unit/test_parser_base.py`

The contract layer. Pure Pydantic + Protocol; no I/O, no DB. Defines what every parser impl produces and the two error classes the worker switches on.

- [ ] **Step 1: Write the failing tests**

Create `api/tests/unit/test_parser_base.py`:

```python
"""Unit tests for the parser contract layer — no I/O, no DB."""

from __future__ import annotations

import pytest

from kpa.integrations.parser.base import (
    CertificationEntry,
    EducationEntry,
    ExperienceEntry,
    ParsedResume,
    ParserError,
    TransientParserError,
)


def test_parsed_resume_defaults_are_safe() -> None:
    """A parser that can only extract raw_text must still produce a valid ParsedResume."""
    pr = ParsedResume(parser_name="library.v1", raw_text="hello world")
    assert pr.schema_version == 1
    assert pr.parser_name == "library.v1"
    assert pr.raw_text == "hello world"
    assert pr.name is None
    assert pr.email is None
    assert pr.phone is None
    assert pr.skills == []
    assert pr.experience == []
    assert pr.education == []
    assert pr.certifications == []


def test_parsed_resume_is_frozen() -> None:
    """Frozen so callers can't mutate after parse — easier to reason about caching later."""
    pr = ParsedResume(parser_name="library.v1", raw_text="x")
    with pytest.raises(Exception):  # pydantic ValidationError on frozen mutation
        pr.email = "x@y.com"  # type: ignore[misc]


def test_parsed_resume_round_trips_through_model_dump() -> None:
    """parsed_json is stored via model_dump(mode='json'); ensure round-trip is stable."""
    pr = ParsedResume(
        parser_name="library.v1",
        raw_text="hello",
        name="Ahamed Wahid",
        email="ahamed@example.com",
        phone="+91-9876543210",
        skills=["python", "fastapi"],
        experience=[
            ExperienceEntry(
                company=None, title=None, start="2020", end="Present", summary="some text"
            )
        ],
        education=[EducationEntry(institution=None, degree="B.Tech", field=None, end_year=2018)],
        certifications=[CertificationEntry(name="AWS SAA", issuer="Amazon", year=2022)],
    )
    dumped = pr.model_dump(mode="json")
    revived = ParsedResume.model_validate(dumped)
    assert revived == pr


def test_parser_error_carries_message() -> None:
    err = ParserError("doc_legacy_not_supported")
    assert str(err) == "doc_legacy_not_supported"


def test_transient_parser_error_is_distinct_class() -> None:
    """Worker autoretry list switches on TransientParserError; ensure it's not a ParserError."""
    err = TransientParserError("storage_timeout")
    assert isinstance(err, TransientParserError)
    assert not isinstance(err, ParserError)
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
cd api
uv run pytest tests/unit/test_parser_base.py -v
```

Expected: `ModuleNotFoundError: No module named 'kpa.integrations.parser'`.

- [ ] **Step 3: Implement the package**

Create `api/src/kpa/integrations/parser/__init__.py`:

```python
"""Resume parser interface + concrete implementations.

The Protocol + ParsedResume schema live in :mod:`.base`. The library/regex
implementation is in :mod:`.library`. A future LLM-backed impl will land in
:mod:`.llm` behind the same Protocol once the provider decision (spec §14 #1)
is resolved.
"""

from kpa.integrations.parser.base import (
    CertificationEntry,
    EducationEntry,
    ExperienceEntry,
    ParsedResume,
    ParserError,
    ResumeParser,
    TransientParserError,
)

__all__ = [
    "CertificationEntry",
    "EducationEntry",
    "ExperienceEntry",
    "ParsedResume",
    "ParserError",
    "ResumeParser",
    "TransientParserError",
]
```

Create `api/src/kpa/integrations/parser/base.py`:

```python
"""Parser contract — Protocol + canonical ParsedResume schema + error types.

Stored in `kpa.resumes.parsed_json` via :meth:`ParsedResume.model_dump`. Any
future parser (LLM, vendor service) MUST produce values that validate against
:class:`ParsedResume`. Bump :attr:`ParsedResume.schema_version` on any breaking
change and own a re-parse migration in the same plan.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict


class ExperienceEntry(BaseModel):
    """One job/role entry. Free-form date strings — parsers don't normalize."""

    company: str | None = None
    title: str | None = None
    start: str | None = None  # "Jan 2020" / "2020" / "01/2020" — free-form
    end: str | None = None  # "Present" / "Dec 2022" / null
    summary: str | None = None


class EducationEntry(BaseModel):
    """One education entry."""

    institution: str | None = None
    degree: str | None = None  # "B.Tech", "M.Sc", "MBA"
    field: str | None = None  # "Computer Science"
    end_year: int | None = None


class CertificationEntry(BaseModel):
    """One certification entry."""

    name: str | None = None
    issuer: str | None = None
    year: int | None = None


class ParsedResume(BaseModel):
    """Canonical parsed-resume payload. Stored verbatim in resumes.parsed_json."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    parser_name: str  # provenance: "library.v1" / "llm.anthropic.v1" / ...
    raw_text: str  # full extracted text, truncated to 64 KB by the extractor

    name: str | None = None
    email: str | None = None
    phone: str | None = None

    skills: list[str] = []
    experience: list[ExperienceEntry] = []
    education: list[EducationEntry] = []
    certifications: list[CertificationEntry] = []


class ResumeParser(Protocol):
    """Async parser: content bytes + mime type in, :class:`ParsedResume` out.

    Raises :class:`ParserError` on permanent failures (corrupt input, unsupported
    type). Raises :class:`TransientParserError` on recoverable failures (transient
    library exceptions, storage hiccups) — the worker autoretries those.
    """

    async def parse(self, *, content: bytes, content_type: str) -> ParsedResume: ...


class ParserError(Exception):
    """Permanent failure — worker marks parse_status='failed' immediately, no retry.

    Message string is a stable slug (e.g. "doc_legacy_not_supported",
    "password_protected", "no_text_extracted", "unsupported_content_type") so it
    can be surfaced verbatim in parse_error without leaking PII.
    """


class TransientParserError(Exception):
    """Recoverable failure — worker autoretries up to 3 times with exponential backoff."""
```

- [ ] **Step 4: Run tests, confirm green**

```bash
uv run pytest tests/unit/test_parser_base.py -v
```

All 5 pass.

- [ ] **Step 5: Lint + types**

```bash
uv run ruff check src/ tests/
uv run mypy
```

Clean. (`Mapped` is unused here; mypy strict should pass.)

- [ ] **Step 6: Commit**

```bash
git add api/src/kpa/integrations/parser/__init__.py \
    api/src/kpa/integrations/parser/base.py \
    api/tests/unit/test_parser_base.py
git commit -m "$(cat <<'EOF'
feat(api): add parser Protocol + ParsedResume schema + error types

ParsedResume is the canonical payload stored in kpa.resumes.parsed_json.
Frozen so callers can't mutate post-parse. schema_version=1 baked in;
a v2 bump owns its own re-parse plan. parser_name field provides
provenance so admin tooling can later filter by which parser produced
each row.

ParserError (permanent, no retry) vs TransientParserError (Celery
autoretry) are separate classes so the @celery_app.task autoretry_for
tuple keys off the type without runtime introspection.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Skills dictionary (`skills_dict.py`)

**Files:**
- Create: `api/src/kpa/integrations/parser/skills_dict.py`
- Create: `api/tests/unit/test_skills_dict.py`

A curated keyword list. Deliberately not exhaustive — the matcher needs *some* skill signal, not perfect coverage. Easy to extend.

- [ ] **Step 1: Write the failing test**

Create `api/tests/unit/test_skills_dict.py`:

```python
"""Sanity checks on the curated skills dictionary."""

from __future__ import annotations

from kpa.integrations.parser.skills_dict import SKILLS


def test_skills_dict_has_minimum_coverage() -> None:
    """The matcher relies on some skill signal — ensure we ship a reasonable set."""
    assert len(SKILLS) >= 150


def test_skills_are_lowercased_and_unique() -> None:
    """The parser does case-insensitive matching and dedupes by lower(); ensure the
    source already is lower so the dedupe is a no-op against this list."""
    lowered = [s.lower() for s in SKILLS]
    assert lowered == list(SKILLS), "dictionary entries must be lowercased"
    assert len(set(SKILLS)) == len(SKILLS), "dictionary entries must be unique"


def test_skills_dict_includes_core_signals() -> None:
    """Smoke test: a handful of well-known skills the matcher should always detect."""
    must_include = {"python", "java", "javascript", "fastapi", "aws", "postgres", "docker"}
    assert must_include.issubset(set(SKILLS))
```

- [ ] **Step 2: Run, confirm fails**

```bash
uv run pytest tests/unit/test_skills_dict.py -v
```

Expected: `ModuleNotFoundError: No module named 'kpa.integrations.parser.skills_dict'`.

- [ ] **Step 3: Implement the dictionary**

Create `api/src/kpa/integrations/parser/skills_dict.py`:

```python
"""Curated skill keyword list for the library resume parser.

Lowercased, unique, sorted. ~200 entries covering languages, frameworks,
data stores, cloud, infra, tooling, ML/AI. Extend liberally; the parser
does case-insensitive substring containment, so spelling variants
(e.g. "node.js" vs "nodejs") should both be listed where common.
"""

from __future__ import annotations

from typing import Final

SKILLS: Final[tuple[str, ...]] = (
    # --- Languages ---
    "bash",
    "c",
    "c#",
    "c++",
    "clojure",
    "css",
    "dart",
    "elixir",
    "erlang",
    "go",
    "golang",
    "groovy",
    "haskell",
    "html",
    "java",
    "javascript",
    "julia",
    "kotlin",
    "lua",
    "matlab",
    "objective-c",
    "ocaml",
    "perl",
    "php",
    "powershell",
    "python",
    "r",
    "ruby",
    "rust",
    "scala",
    "shell",
    "sql",
    "swift",
    "typescript",
    "vb.net",
    "zsh",
    # --- Web frameworks (backend) ---
    "asp.net",
    "django",
    "express",
    "fastapi",
    "flask",
    "gin",
    "koa",
    "laravel",
    "nestjs",
    "node.js",
    "nodejs",
    "phoenix",
    "rails",
    "spring",
    "spring boot",
    "tornado",
    # --- Web frameworks (frontend) ---
    "angular",
    "ember",
    "next.js",
    "nextjs",
    "nuxt",
    "react",
    "react native",
    "redux",
    "remix",
    "solid.js",
    "svelte",
    "tailwind",
    "vite",
    "vue",
    "vue.js",
    "webpack",
    # --- Mobile ---
    "android",
    "flutter",
    "ios",
    "jetpack compose",
    "swiftui",
    "xamarin",
    # --- Data / DBs ---
    "bigquery",
    "cassandra",
    "clickhouse",
    "cockroachdb",
    "couchbase",
    "dynamodb",
    "elasticsearch",
    "hbase",
    "kafka",
    "mariadb",
    "mongodb",
    "mssql",
    "mysql",
    "neo4j",
    "opensearch",
    "oracle",
    "pgvector",
    "postgres",
    "postgresql",
    "rabbitmq",
    "redis",
    "redshift",
    "snowflake",
    "spark",
    "sqlite",
    "trino",
    # --- Cloud ---
    "aws",
    "azure",
    "cloudflare",
    "digitalocean",
    "fly.io",
    "gcp",
    "google cloud",
    "heroku",
    "linode",
    "render",
    "vercel",
    # --- Infra / DevOps ---
    "ansible",
    "argocd",
    "circleci",
    "docker",
    "elk",
    "fluent bit",
    "github actions",
    "gitlab ci",
    "grafana",
    "helm",
    "istio",
    "jenkins",
    "kubernetes",
    "linkerd",
    "loki",
    "nginx",
    "opentelemetry",
    "packer",
    "prometheus",
    "puppet",
    "saltstack",
    "tempo",
    "terraform",
    "vault",
    # --- API / messaging ---
    "graphql",
    "grpc",
    "openapi",
    "rest",
    "soap",
    "websocket",
    # --- Auth / security ---
    "jwt",
    "oauth",
    "oauth2",
    "oidc",
    "saml",
    # --- ML / AI ---
    "huggingface",
    "keras",
    "langchain",
    "llamaindex",
    "mlflow",
    "numpy",
    "pandas",
    "pytorch",
    "scikit-learn",
    "spacy",
    "tensorflow",
    "transformers",
    "xgboost",
    # --- Testing ---
    "cypress",
    "jest",
    "junit",
    "mocha",
    "playwright",
    "pytest",
    "selenium",
    "testng",
    "vitest",
    # --- ORMs / clients ---
    "alembic",
    "django orm",
    "hibernate",
    "jdbi",
    "knex",
    "prisma",
    "sequelize",
    "sqlalchemy",
    "typeorm",
    # --- Methodologies / other ---
    "agile",
    "ci/cd",
    "ddd",
    "event sourcing",
    "kanban",
    "microservices",
    "scrum",
    "tdd",
    "uml",
)
```

(Count: ~190 entries. Hand-verify it's `>= 150` and `sorted` per the tests.)

- [ ] **Step 4: Run, confirm green**

```bash
uv run pytest tests/unit/test_skills_dict.py -v
```

All 3 pass.

- [ ] **Step 5: Lint + types**

```bash
uv run ruff check src/ tests/
uv run mypy
```

Clean.

- [ ] **Step 6: Commit**

```bash
git add api/src/kpa/integrations/parser/skills_dict.py api/tests/unit/test_skills_dict.py
git commit -m "$(cat <<'EOF'
feat(api): add curated skill keyword dictionary for library parser

~190 lowercased + sorted entries covering languages, frameworks,
data, cloud, infra, ML, testing, ORMs. Deliberately not exhaustive
— the matcher needs some skill signal, not perfect coverage. The
parser does case-insensitive containment; spelling variants like
"node.js" vs "nodejs" are both listed where common.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Text extraction — `extract_text()` over PDF / DOCX

**Files:**
- Create: `api/src/kpa/integrations/parser/text.py`
- Create: `api/tests/unit/test_parser_text.py`

Pure-function text extraction. PDF: `pypdf` first (fast), fall back to `pdfminer.six` if the result is empty/garbled. DOCX: `python-docx`. Errors are classified into `ParserError` (permanent) vs `TransientParserError` (worker should retry).

- [ ] **Step 1: Write the failing tests**

Create `api/tests/unit/test_parser_text.py`:

```python
"""Unit tests for extract_text() — uses fpdf2 + python-docx to generate fixtures in-process."""

from __future__ import annotations

import io

import pytest
from docx import Document
from fpdf import FPDF
from pypdf import PdfReader, PdfWriter

from kpa.integrations.parser.base import ParserError
from kpa.integrations.parser.text import MAX_TEXT_BYTES, extract_text

# --- Fixture generators (in-process; no binary commits) ---


def _make_pdf(text_lines: list[str]) -> bytes:
    """Generate a minimal PDF with the given text lines."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in text_lines:
        pdf.cell(text=line, new_x="LMARGIN", new_y="NEXT")
    out = pdf.output()
    return bytes(out)


def _make_docx(text_lines: list[str]) -> bytes:
    """Generate a minimal DOCX with the given paragraphs."""
    doc = Document()
    for line in text_lines:
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_password_protected_pdf(text: str, password: str) -> bytes:
    src = _make_pdf([text])
    reader = PdfReader(io.BytesIO(src))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(user_password=password)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_blank_pdf() -> bytes:
    """PDF with a page but no text content — simulates an image-only resume."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# --- Tests ---


async def test_extract_text_from_pdf() -> None:
    pdf_bytes = _make_pdf(["Hello world", "Second line"])
    text = await extract_text(content=pdf_bytes, content_type="application/pdf")
    assert "Hello world" in text
    assert "Second line" in text


async def test_extract_text_from_docx() -> None:
    docx_bytes = _make_docx(["Hello world", "Second paragraph"])
    text = await extract_text(
        content=docx_bytes,
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )
    assert "Hello world" in text
    assert "Second paragraph" in text


async def test_extract_text_rejects_legacy_doc() -> None:
    with pytest.raises(ParserError, match="doc_legacy_not_supported"):
        await extract_text(content=b"\xd0\xcf\x11\xe0", content_type="application/msword")


async def test_extract_text_rejects_unsupported_content_type() -> None:
    with pytest.raises(ParserError, match="unsupported_content_type"):
        await extract_text(content=b"random", content_type="image/png")


async def test_extract_text_rejects_password_protected_pdf() -> None:
    pdf_bytes = _make_password_protected_pdf("secret content", password="abc")
    with pytest.raises(ParserError, match="password_protected"):
        await extract_text(content=pdf_bytes, content_type="application/pdf")


async def test_extract_text_rejects_image_only_pdf() -> None:
    """Blank page → no extractable text → both pypdf + pdfminer return empty → ParserError."""
    pdf_bytes = _make_blank_pdf()
    with pytest.raises(ParserError, match="no_text_extracted"):
        await extract_text(content=pdf_bytes, content_type="application/pdf")


async def test_extract_text_truncates_to_max_bytes() -> None:
    long_line = "x" * 100  # 100 bytes per line
    pdf_bytes = _make_pdf([long_line] * 1000)  # ~100 KB of text — over the 64KB cap
    text = await extract_text(content=pdf_bytes, content_type="application/pdf")
    assert len(text.encode("utf-8")) <= MAX_TEXT_BYTES
```

- [ ] **Step 2: Run, confirm fails**

```bash
cd api
uv run pytest tests/unit/test_parser_text.py -v
```

Expected: `ModuleNotFoundError: No module named 'kpa.integrations.parser.text'`.

- [ ] **Step 3: Implement extract_text**

Create `api/src/kpa/integrations/parser/text.py`:

```python
"""PDF + DOCX → plain text. Pure-function; raises classified errors.

PDF strategy: pypdf first (fast, handles most modern PDFs). If the result
looks empty/garbled (heuristic: total length < 50 chars after stripping),
fall back to pdfminer.six (slower, more layout-tolerant). If both fail,
raise ParserError("no_text_extracted").

DOCX strategy: python-docx. Walk paragraphs and table cells, join with newlines.

Legacy .doc (binary Word) is explicitly rejected as
ParserError("doc_legacy_not_supported") — parsing it needs antiword or
LibreOffice (binary deps); deferred to a later plan.
"""

from __future__ import annotations

import io
from typing import Final

import anyio.to_thread
import pypdf
import pypdf.errors
from docx import Document
from pdfminer.high_level import extract_text as pdfminer_extract
from pdfminer.pdfparser import PDFSyntaxError

from kpa.integrations.parser.base import ParserError, TransientParserError

PDF_CONTENT_TYPE: Final[str] = "application/pdf"
DOCX_CONTENT_TYPE: Final[str] = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
LEGACY_DOC_CONTENT_TYPE: Final[str] = "application/msword"

MAX_TEXT_BYTES: Final[int] = 64 * 1024  # 64 KB cap on extracted text
_EMPTY_THRESHOLD: Final[int] = 50  # pypdf result shorter than this → try pdfminer


async def extract_text(*, content: bytes, content_type: str) -> str:
    """Extract plain text from a resume blob. Truncated to MAX_TEXT_BYTES."""
    if content_type == LEGACY_DOC_CONTENT_TYPE:
        raise ParserError("doc_legacy_not_supported")
    if content_type == PDF_CONTENT_TYPE:
        text = await anyio.to_thread.run_sync(_extract_pdf, content)
        return _truncate(text)
    if content_type == DOCX_CONTENT_TYPE:
        text = await anyio.to_thread.run_sync(_extract_docx, content)
        return _truncate(text)
    raise ParserError("unsupported_content_type")


def _extract_pdf(content: bytes) -> str:
    """Try pypdf; fall back to pdfminer if the result is empty/garbled."""
    pypdf_text = _extract_pdf_pypdf(content)
    if len(pypdf_text.strip()) >= _EMPTY_THRESHOLD:
        return pypdf_text

    pdfminer_text = _extract_pdf_pdfminer(content)
    if len(pdfminer_text.strip()) >= _EMPTY_THRESHOLD:
        return pdfminer_text

    # Both extractors returned ~nothing. Image-only / scanned PDF.
    raise ParserError("no_text_extracted")


def _extract_pdf_pypdf(content: bytes) -> str:
    try:
        reader = pypdf.PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise ParserError("password_protected")
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ParserError:
        raise
    except pypdf.errors.PdfReadError as exc:
        # Often "EOF marker not found", malformed xref, etc. — permanent.
        raise ParserError("pdf_read_error") from exc
    except Exception as exc:  # noqa: BLE001 — unknown library bug; treat as transient
        raise TransientParserError(f"pypdf_unexpected: {type(exc).__name__}") from exc


def _extract_pdf_pdfminer(content: bytes) -> str:
    try:
        return pdfminer_extract(io.BytesIO(content)) or ""
    except PDFSyntaxError as exc:
        raise ParserError("pdf_syntax_error") from exc
    except Exception as exc:  # noqa: BLE001
        raise TransientParserError(f"pdfminer_unexpected: {type(exc).__name__}") from exc


def _extract_docx(content: bytes) -> str:
    try:
        doc = Document(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001 — python-docx raises generic Exception variants
        raise ParserError("docx_read_error") from exc

    lines: list[str] = []
    for para in doc.paragraphs:
        if para.text:
            lines.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text:
                    lines.append(cell.text)
    text = "\n".join(lines)
    if not text.strip():
        raise ParserError("no_text_extracted")
    return text


def _truncate(text: str) -> str:
    """Truncate to MAX_TEXT_BYTES of UTF-8 — never split mid-codepoint."""
    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_TEXT_BYTES:
        return text
    # Decode with errors='ignore' drops any partial codepoint at the cut.
    return encoded[:MAX_TEXT_BYTES].decode("utf-8", errors="ignore")
```

- [ ] **Step 4: Run tests, confirm green**

```bash
uv run pytest tests/unit/test_parser_text.py -v
```

All 7 pass.

If `test_extract_text_rejects_image_only_pdf` fails because pypdf returns `'\n'` from a blank page (not strictly empty), check: the threshold is `_EMPTY_THRESHOLD = 50` and `.strip()` removes whitespace, so `'\n'.strip()` is `''` length 0 → falls through to pdfminer → which returns empty → falls through to `ParserError("no_text_extracted")`. Good.

If `test_extract_text_from_pdf` fails because fpdf2's PDF output uses font encoding pypdf doesn't decode, you may need to adjust the assertions (e.g., assert tokens individually rather than the full line). Document this in the test if it happens.

- [ ] **Step 5: Lint + types**

```bash
uv run ruff check src/ tests/
uv run mypy
```

Clean. If mypy complains about pdfminer/docx stubs missing, add to `[tool.mypy]` in pyproject.toml:

```toml
[[tool.mypy.overrides]]
module = ["pdfminer.*", "docx.*", "fpdf.*"]
ignore_missing_imports = true
```

- [ ] **Step 6: Commit**

```bash
git add api/src/kpa/integrations/parser/text.py api/tests/unit/test_parser_text.py api/pyproject.toml
git commit -m "$(cat <<'EOF'
feat(api): add extract_text() — pypdf+pdfminer for PDF, python-docx for DOCX

Two-tier PDF strategy: pypdf first (fast, modern PDFs), fall back to
pdfminer.six (layout-tolerant, slower) if pypdf returns <50 chars.
Both empty → ParserError("no_text_extracted") — that's the image-only
/ scanned-resume case.

DOCX reads paragraphs + table cells. Legacy .doc explicitly rejected
as ParserError("doc_legacy_not_supported") until antiword/LibreOffice
deps land.

Truncation cap of 64 KB; UTF-8-aware so we never split mid-codepoint.
Errors are classified: ParserError for permanent (corrupt, encrypted,
unsupported), TransientParserError for unexpected library exceptions
worth Celery autoretry.

Unit tests generate PDF/DOCX fixtures in-process via fpdf2 +
python-docx — no binary commits.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `LibraryResumeParser` — regex + keyword impl

**Files:**
- Create: `api/src/kpa/integrations/parser/library.py`
- Create: `api/tests/unit/test_parser_library.py`

Concrete `ResumeParser` impl using the contract layer + text extraction + skills dictionary.

- [ ] **Step 1: Write the failing tests**

Create `api/tests/unit/test_parser_library.py`:

```python
"""Unit tests for LibraryResumeParser — exercises regex + dictionary logic.

Tests feed in canned PDF/DOCX bytes (generated via fpdf2 / python-docx) and
assert the ParsedResume shape. Heuristics for name/experience/education are
intentionally loose; tests assert what the regex CAN find, not what's correct.
"""

from __future__ import annotations

import io

import pytest
from docx import Document
from fpdf import FPDF

from kpa.integrations.parser.base import ParsedResume
from kpa.integrations.parser.library import LibraryResumeParser

PDF_CT = "application/pdf"
DOCX_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _pdf(text_lines: list[str]) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in text_lines:
        pdf.cell(text=line, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def _docx(text_lines: list[str]) -> bytes:
    doc = Document()
    for line in text_lines:
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def parser() -> LibraryResumeParser:
    return LibraryResumeParser()


async def test_parse_returns_parsed_resume_with_parser_name(
    parser: LibraryResumeParser,
) -> None:
    pr = await parser.parse(content=_pdf(["hello"]), content_type=PDF_CT)
    assert isinstance(pr, ParsedResume)
    assert pr.parser_name == "library.v1"
    assert pr.schema_version == 1
    assert "hello" in pr.raw_text


async def test_parse_extracts_email(parser: LibraryResumeParser) -> None:
    pr = await parser.parse(
        content=_pdf(["Ahamed Wahid", "Contact: ahamed.wahid@example.com"]),
        content_type=PDF_CT,
    )
    assert pr.email == "ahamed.wahid@example.com"


async def test_parse_extracts_indian_phone(parser: LibraryResumeParser) -> None:
    pr = await parser.parse(
        content=_pdf(["Name: A", "Phone: +91-98765-43210"]), content_type=PDF_CT
    )
    assert pr.phone is not None
    # Stripped of separators, the digits should match the input.
    digits = "".join(ch for ch in pr.phone if ch.isdigit() or ch == "+")
    assert "9876543210" in digits


async def test_parse_extracts_intl_phone(parser: LibraryResumeParser) -> None:
    pr = await parser.parse(
        content=_pdf(["Name: A", "Mobile: +1 415 555 0123"]), content_type=PDF_CT
    )
    assert pr.phone is not None


async def test_parse_extracts_skills_from_dictionary(parser: LibraryResumeParser) -> None:
    pr = await parser.parse(
        content=_pdf(
            [
                "Senior Engineer",
                "Skills: Python, FastAPI, Postgres, Docker, Kubernetes",
            ]
        ),
        content_type=PDF_CT,
    )
    assert set(pr.skills) >= {"python", "fastapi", "postgres", "docker", "kubernetes"}


async def test_parse_skills_are_deduped_and_sorted(parser: LibraryResumeParser) -> None:
    pr = await parser.parse(
        content=_pdf(["python python PYTHON fastapi FastAPI", "more python"]),
        content_type=PDF_CT,
    )
    assert pr.skills == sorted(set(pr.skills))
    assert pr.skills.count("python") == 1


async def test_parse_finds_experience_date_ranges(parser: LibraryResumeParser) -> None:
    pr = await parser.parse(
        content=_pdf(
            [
                "Experience",
                "Acme Corp: Jan 2020 to Dec 2022 — built things",
                "BetaWorks: 2018 - 2020 — Senior Eng",
            ]
        ),
        content_type=PDF_CT,
    )
    assert len(pr.experience) >= 1
    # The regex should pick up at least one start/end pair.
    has_range = any(e.start is not None and e.end is not None for e in pr.experience)
    assert has_range


async def test_parse_finds_education_degree(parser: LibraryResumeParser) -> None:
    pr = await parser.parse(
        content=_pdf(["Education", "B.Tech, IIT Bombay, 2018"]), content_type=PDF_CT
    )
    assert any(e.degree is not None for e in pr.education)
    assert any(e.end_year == 2018 for e in pr.education)


async def test_parse_empty_resume_returns_valid_parsed_resume(
    parser: LibraryResumeParser,
) -> None:
    """A resume with only whitespace still produces a valid ParsedResume
    (no exceptions; empty arrays for everything except raw_text)."""
    pr = await parser.parse(content=_pdf(["   "]), content_type=PDF_CT)
    assert pr.email is None
    assert pr.phone is None
    assert pr.skills == []
    assert pr.experience == []
    assert pr.education == []


async def test_parse_works_on_docx(parser: LibraryResumeParser) -> None:
    pr = await parser.parse(
        content=_docx(["Name", "Email: a@b.com", "Skills: Java, Spring Boot"]),
        content_type=DOCX_CT,
    )
    assert pr.email == "a@b.com"
    assert {"java", "spring boot"}.issubset(set(pr.skills))


async def test_parse_finds_certification(parser: LibraryResumeParser) -> None:
    pr = await parser.parse(
        content=_pdf(["Certifications", "AWS Certified Solutions Architect, 2022"]),
        content_type=PDF_CT,
    )
    assert any(c.year == 2022 for c in pr.certifications)
```

- [ ] **Step 2: Run tests, confirm fails**

```bash
uv run pytest tests/unit/test_parser_library.py -v
```

Expected: `ModuleNotFoundError: No module named 'kpa.integrations.parser.library'`.

- [ ] **Step 3: Implement LibraryResumeParser**

Create `api/src/kpa/integrations/parser/library.py`:

```python
"""LibraryResumeParser — regex + keyword extraction, no external services.

Best-effort across the full §6.1 schema. Empty arrays where regex can't find
anything. The LLM impl that lands later replaces this with higher-fidelity
extraction behind the same Protocol.
"""

from __future__ import annotations

import re
from typing import Final

from kpa.integrations.parser.base import (
    CertificationEntry,
    EducationEntry,
    ExperienceEntry,
    ParsedResume,
)
from kpa.integrations.parser.skills_dict import SKILLS
from kpa.integrations.parser.text import extract_text

PARSER_NAME: Final[str] = "library.v1"

# --- Regex patterns ---

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Indian + international phone. Tolerates spaces, dashes, parentheses.
# Requires at least 10 digits in a row (ignoring separators).
_PHONE_RE = re.compile(
    r"""
    (?:                                     # one of:
        \+\d{1,3}[\s\-]?                    #   country code with separator
      | \(\+?\d{1,3}\)[\s\-]?               #   country code in parens
      | (?<![\d])                           #   or no country code (boundary on digit)
    )
    (?:\d[\s\-]?){9,14}\d                   # 10–15 total digits with optional separators
    """,
    re.VERBOSE,
)

_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*"
_YEAR = r"\d{4}"
_DATE = rf"(?:(?:{_MONTH})\s+)?{_YEAR}"

# "Jan 2020 - Dec 2022" / "2018 to 2020" / "Mar 2021 – Present"
_EXPERIENCE_RANGE_RE = re.compile(
    rf"({_DATE})\s*(?:-|–|to|until)\s*({_DATE}|Present|present|Current|current)",
)

_DEGREE_RE = re.compile(
    r"\b(B\.?\s*Tech|B\.?\s*E|B\.?\s*Sc|B\.?\s*A|"
    r"M\.?\s*Tech|M\.?\s*Sc|M\.?\s*B\.?\s*A|MBA|PhD|Ph\.D)\b",
    re.IGNORECASE,
)
_YEAR_NEARBY_RE = re.compile(r"\b(19|20)\d{2}\b")

_CERT_LINE_RE = re.compile(r"(certif(?:ied|ication)[^\n]*)", re.IGNORECASE)


class LibraryResumeParser:
    """Regex/keyword-based parser. parser_name='library.v1'."""

    async def parse(self, *, content: bytes, content_type: str) -> ParsedResume:
        raw_text = await extract_text(content=content, content_type=content_type)

        return ParsedResume(
            parser_name=PARSER_NAME,
            raw_text=raw_text,
            name=_extract_name(raw_text),
            email=_extract_email(raw_text),
            phone=_extract_phone(raw_text),
            skills=_extract_skills(raw_text),
            experience=_extract_experience(raw_text),
            education=_extract_education(raw_text),
            certifications=_extract_certifications(raw_text),
        )


# --- Field extractors ---


def _extract_name(text: str) -> str | None:
    """Heuristic: first non-empty line with ≤5 capitalised words and no digits/@."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or "@" in stripped or any(ch.isdigit() for ch in stripped):
            continue
        tokens = stripped.split()
        if 1 <= len(tokens) <= 5 and all(t[0].isupper() for t in tokens if t.isalpha()):
            return stripped
    return None


def _extract_email(text: str) -> str | None:
    m = _EMAIL_RE.search(text)
    return m.group(0) if m else None


def _extract_phone(text: str) -> str | None:
    m = _PHONE_RE.search(text)
    return m.group(0).strip() if m else None


def _extract_skills(text: str) -> list[str]:
    """Case-insensitive containment against the curated SKILLS dictionary."""
    lower = text.lower()
    found = {skill for skill in SKILLS if skill in lower}
    return sorted(found)


def _extract_experience(text: str) -> list[ExperienceEntry]:
    entries: list[ExperienceEntry] = []
    for match in _EXPERIENCE_RANGE_RE.finditer(text):
        start, end = match.group(1), match.group(2)
        # Grab ±50 chars of surrounding context for `summary`.
        ctx_start = max(0, match.start() - 50)
        ctx_end = min(len(text), match.end() + 50)
        summary = text[ctx_start:ctx_end].strip().replace("\n", " ")
        entries.append(
            ExperienceEntry(company=None, title=None, start=start, end=end, summary=summary)
        )
    return entries


def _extract_education(text: str) -> list[EducationEntry]:
    entries: list[EducationEntry] = []
    for match in _DEGREE_RE.finditer(text):
        degree = match.group(1)
        # Find a year within 60 chars after the degree.
        tail = text[match.end() : match.end() + 60]
        year_match = _YEAR_NEARBY_RE.search(tail)
        end_year = int(year_match.group(0)) if year_match else None
        entries.append(
            EducationEntry(institution=None, degree=degree, field=None, end_year=end_year)
        )
    return entries


def _extract_certifications(text: str) -> list[CertificationEntry]:
    entries: list[CertificationEntry] = []
    for match in _CERT_LINE_RE.finditer(text):
        line = match.group(1)
        year_match = _YEAR_NEARBY_RE.search(line)
        year = int(year_match.group(0)) if year_match else None
        entries.append(CertificationEntry(name=line.strip(), issuer=None, year=year))
    return entries
```

- [ ] **Step 4: Run tests, confirm green**

```bash
uv run pytest tests/unit/test_parser_library.py -v
```

All 11 pass.

If `test_parse_finds_education_degree` fails on `end_year == 2018`: the regex's "year nearby" window is 60 chars after the degree. Adjust if the test text format doesn't fall within that window.

If `test_parse_finds_experience_date_ranges` fails: the date-range regex requires a separator (`-`, `–`, `to`, `until`). Check that the test text uses one of those.

- [ ] **Step 5: Lint + types**

```bash
uv run ruff check src/ tests/
uv run mypy
```

Clean.

- [ ] **Step 6: Commit**

```bash
git add api/src/kpa/integrations/parser/library.py api/tests/unit/test_parser_library.py
git commit -m "$(cat <<'EOF'
feat(api): add LibraryResumeParser — regex + keyword extraction

parser_name="library.v1". Best-effort across the full §6.1 schema.
- email/phone via regex (Indian + international phone formats)
- skills via case-insensitive containment against SKILLS dictionary
- experience via date-range regex; surrounding ±50 chars become summary
  (company/title left null — those need LLM)
- education via degree-keyword regex + year-nearby capture
- certifications via "Certif(ied|ication)" line capture + year

Empty arrays where regex can't find anything. Tests confirm the parser
produces a valid ParsedResume even when no fields match.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Celery app + per-worker engine

**Files:**
- Create: `api/src/kpa/workers/__init__.py`
- Create: `api/src/kpa/workers/celery_app.py`

Celery instance, broker config, lifecycle hooks. The `worker_process_init` signal builds the async engine + sessionmaker once per worker process; `get_session_maker()` is what task bodies call.

No tests in this task — the public surface is `celery_app` itself, and exercising it requires either a real worker or eager mode, both of which the *parse task* tests in Task 8 cover.

- [ ] **Step 1: Create the package skeleton**

Create `api/src/kpa/workers/__init__.py`:

```python
"""Celery workers — separate process from uvicorn.

Each task module under :mod:`.tasks` is included via the `include` arg in
:mod:`.celery_app`. The Celery instance is `kpa.workers.celery_app.celery_app`.
"""
```

- [ ] **Step 2: Create the Celery app**

Create `api/src/kpa/workers/celery_app.py`:

```python
"""Celery instance + broker config + per-worker DB engine lifecycle.

Run a worker (from `api/`):

    uv run --env-file=.env celery -A kpa.workers.celery_app worker \\
        --pool=solo --concurrency=1 -Q parse

--pool=solo is the MVP choice: single-concurrency, no subprocess fan-out,
plays cleanly with `asyncio.run()` in the task body. P5 hardening switches
to --pool=prefork + per-process engine without changes here (the
worker_process_init signal handles both).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from celery import Celery
from celery.signals import worker_process_init, worker_shutting_down

from kpa.settings import Settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

# Settings is built at import time — one Settings object for the worker process.
# Tasks read this rather than instantiating Settings repeatedly.
settings = Settings()

celery_app = Celery(
    "kpa",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["kpa.workers.tasks.parse"],
)

celery_app.conf.update(
    task_default_queue="parse",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
    broker_connection_retry_on_startup=True,
    result_expires=3600,  # 1h — most jobs surface state via DB row, not result
)


# --- Per-worker engine + sessionmaker ---

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


@worker_process_init.connect
def _init_engine(**_kwargs: object) -> None:
    """Build the async engine + sessionmaker once per worker process.

    Works with --pool=solo (single process) AND --pool=prefork (one signal
    per subprocess) — each subprocess gets its own engine.
    """
    global _engine, _sessionmaker
    from kpa.db.session import create_engine_from_settings, make_sessionmaker

    _engine = create_engine_from_settings(settings)
    _sessionmaker = make_sessionmaker(_engine)


@worker_shutting_down.connect
def _dispose_engine(**_kwargs: object) -> None:
    """Dispose the engine on graceful shutdown so asyncpg releases connections."""
    if _engine is not None:
        asyncio.run(_engine.dispose())


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Return the worker's sessionmaker.

    In eager mode (tests), the worker_process_init signal doesn't fire because
    no worker process exists — build a fresh sessionmaker on demand. The settings
    object's redis_url isn't used in eager mode, but the DB url is.
    """
    global _engine, _sessionmaker
    if _sessionmaker is None:
        from kpa.db.session import create_engine_from_settings, make_sessionmaker

        _engine = create_engine_from_settings(settings)
        _sessionmaker = make_sessionmaker(_engine)
    return _sessionmaker
```

- [ ] **Step 3: Smoke import the module**

```bash
cd api
KPA_REDIS_URL=redis://localhost:6379/0 \
KPA_ENV=local KPA_SERVICE_NAME=kpa-api \
KPA_DB_URL=postgresql+asyncpg://u:p@h:5432/d \
uv run python -c "
from kpa.workers.celery_app import celery_app, get_session_maker
print('celery app name:', celery_app.main)
print('default queue:', celery_app.conf.task_default_queue)
print('broker:', celery_app.conf.broker_url[:20] + '...')
"
```

Expected:
```
celery app name: kpa
default queue: parse
broker: redis://localhost:6...
```

- [ ] **Step 4: Lint + types + existing tests still green**

```bash
uv run ruff check src/ tests/
uv run mypy
uv run pytest -v
```

All clean and passing (still 28 tests — no new tests added here; Task 8 covers the task body).

- [ ] **Step 5: Commit**

```bash
git add api/src/kpa/workers/__init__.py api/src/kpa/workers/celery_app.py
git commit -m "$(cat <<'EOF'
feat(api): add Celery app + per-worker DB engine lifecycle

Single celery_app instance keyed off KPA_REDIS_URL. Default queue is
'parse'; task_acks_late + worker_prefetch_multiplier=1 prevent the
worker from grabbing extra work it can't finish. task_always_eager
honors KPA_CELERY_TASK_ALWAYS_EAGER so tests can run task bodies
inline without a broker.

worker_process_init signal builds the AsyncEngine + sessionmaker
once per worker process (works with --pool=solo today and
--pool=prefork later without changes). get_session_maker() also
lazy-builds in eager mode where no worker_process_init fires.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: `parse_resume` task — 3-txn split, retry, idempotency

**Files:**
- Create: `api/src/kpa/workers/tasks/__init__.py`
- Create: `api/src/kpa/workers/tasks/parse.py`
- Create: `api/tests/unit/test_parse_task.py`

The core of the plan. Sync Celery task wraps `asyncio.run()`; the async body does load+gate → mark parsing → extract+parse (no DB) → persist final. Idempotency at three places, typed-error retry policy, capped retries.

- [ ] **Step 1: Write the failing tests**

Create `api/tests/unit/test_parse_task.py`:

```python
"""Unit tests for the parse task body — direct calls to _parse_resume_async with
mocked storage + an in-memory sessionmaker. No Redis, no real Celery dispatch."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from kpa.db.models import Applicant, Resume, ResumeParseStatus, User, UserRole
from kpa.integrations.parser.base import (
    ParsedResume,
    ParserError,
    ResumeParser,
    TransientParserError,
)
from kpa.workers.tasks.parse import _parse_resume_async

pytestmark = pytest.mark.integration  # uses local Postgres for the session


@pytest_asyncio.fixture
async def sm() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Per-test sessionmaker bound to a fresh asyncpg connection."""
    import os

    url = os.environ.get("KPA_TEST_DB_URL", "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa_test")
    engine = create_async_engine(url, poolclass=NullPool)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _make_resume_row(
    sm: async_sessionmaker[AsyncSession],
    *,
    status: ResumeParseStatus = ResumeParseStatus.PENDING,
) -> UUID:
    """Create a user + applicant + resume row; return resume id."""
    async with sm() as session:
        user = User(email=f"{uuid4()}@ex.com", role=UserRole.APPLICANT)
        session.add(user)
        await session.flush()
        applicant = Applicant(user_id=user.id, full_name="Test")
        session.add(applicant)
        await session.flush()
        resume = Resume(
            applicant_id=applicant.id,
            storage_key=f"resumes/{uuid4()}.pdf",
            original_filename="cv.pdf",
            content_type="application/pdf",
            size_bytes=100,
            parse_status=status,
        )
        session.add(resume)
        await session.commit()
        return resume.id


class _FakeStorage:
    """Returns canned bytes regardless of key."""

    def __init__(self, content: bytes = b"PDFBYTES") -> None:
        self.content = content
        self.read_calls = 0

    async def read(self, key: str) -> bytes:
        self.read_calls += 1
        return self.content

    async def save(self, *, key: str, content: bytes, content_type: str) -> None:
        pass

    async def delete(self, key: str) -> None:
        pass


class _FakeParser:
    """Returns a canned ParsedResume."""

    def __init__(self, result: ParsedResume) -> None:
        self.result = result
        self.parse_calls = 0

    async def parse(self, *, content: bytes, content_type: str) -> ParsedResume:
        self.parse_calls += 1
        return self.result


class _RaisingParser:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    async def parse(self, *, content: bytes, content_type: str) -> ParsedResume:
        raise self.exc


async def test_parse_happy_path_persists_parsed_json(
    sm: async_sessionmaker[AsyncSession],
) -> None:
    resume_id = await _make_resume_row(sm)
    storage = _FakeStorage()
    parser = _FakeParser(
        ParsedResume(parser_name="library.v1", raw_text="hello", email="a@b.com")
    )

    await _parse_resume_async(resume_id, sm=sm, storage=storage, parser=parser)

    async with sm() as session:
        row = await session.get(Resume, resume_id)
        assert row is not None
        assert row.parse_status == ResumeParseStatus.PARSED
        assert row.parsed_json is not None
        assert row.parsed_json["email"] == "a@b.com"
        assert row.parsed_json["parser_name"] == "library.v1"
        assert row.parse_error is None
    assert storage.read_calls == 1
    assert parser.parse_calls == 1


async def test_parse_parser_error_marks_failed_no_retry(
    sm: async_sessionmaker[AsyncSession],
) -> None:
    resume_id = await _make_resume_row(sm)
    storage = _FakeStorage()
    parser = _RaisingParser(ParserError("password_protected"))

    # ParserError doesn't propagate — task handles it by marking failed.
    await _parse_resume_async(resume_id, sm=sm, storage=storage, parser=parser)

    async with sm() as session:
        row = await session.get(Resume, resume_id)
        assert row is not None
        assert row.parse_status == ResumeParseStatus.FAILED
        assert row.parse_error == "password_protected"


async def test_parse_transient_error_propagates_for_celery_retry(
    sm: async_sessionmaker[AsyncSession],
) -> None:
    resume_id = await _make_resume_row(sm)
    storage = _FakeStorage()
    parser = _RaisingParser(TransientParserError("storage_blip"))

    with pytest.raises(TransientParserError):
        await _parse_resume_async(resume_id, sm=sm, storage=storage, parser=parser)

    # Row is still in 'parsing' state — the next retry will pick it up.
    # (No commit happens after the parse failure in the transient path.)
    async with sm() as session:
        row = await session.get(Resume, resume_id)
        assert row is not None
        assert row.parse_status == ResumeParseStatus.PARSING


@pytest.mark.parametrize(
    "initial_status",
    [ResumeParseStatus.PARSED, ResumeParseStatus.FAILED, ResumeParseStatus.PARSING],
)
async def test_parse_idempotent_on_terminal_or_in_progress_status(
    sm: async_sessionmaker[AsyncSession],
    initial_status: ResumeParseStatus,
) -> None:
    """If the row is already parsed/failed/parsing, the task no-ops."""
    resume_id = await _make_resume_row(sm, status=initial_status)
    storage = _FakeStorage()
    parser = _FakeParser(ParsedResume(parser_name="library.v1", raw_text="x"))

    await _parse_resume_async(resume_id, sm=sm, storage=storage, parser=parser)

    async with sm() as session:
        row = await session.get(Resume, resume_id)
        assert row is not None
        assert row.parse_status == initial_status
        # Parser was NOT called — no work done.
    assert parser.parse_calls == 0


async def test_parse_missing_row_is_silent(
    sm: async_sessionmaker[AsyncSession],
) -> None:
    """Worker invoked for a deleted row — log + return, no exception."""
    fake_id = uuid4()
    storage = _FakeStorage()
    parser = _FakeParser(ParsedResume(parser_name="library.v1", raw_text="x"))

    # Should not raise.
    await _parse_resume_async(fake_id, sm=sm, storage=storage, parser=parser)

    assert parser.parse_calls == 0
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
uv run pytest tests/unit/test_parse_task.py -v -m integration
```

Expected: `ModuleNotFoundError: No module named 'kpa.workers.tasks'`.

- [ ] **Step 3: Implement the task package + body**

Create `api/src/kpa/workers/tasks/__init__.py`:

```python
"""Celery task modules. Each module under here is included by celery_app."""
```

Create `api/src/kpa/workers/tasks/parse.py`:

```python
"""parse_resume task — extract text, parse to structured JSON, persist.

Sync Celery entry point wraps an asyncio body via :func:`asyncio.run`. The
async body splits work into three transactions:

1. Load + idempotency gate + mark `parse_status=parsing` (commit). Holds a
   short row lock only.
2. (no DB) Read bytes from storage, call extract_text(), call parser.parse().
   Can take seconds; no row lock held.
3. Re-load row inside a fresh session, verify it's still `parsing`, write
   `parsed_json` + `parse_status=parsed`, commit.

ParserError → permanent failure → `parse_status=failed` immediately, no retry.
TransientParserError → propagated → Celery autoretry (up to 3 with backoff).
Any other unexpected exception → wrapped → retried up to max_retries.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from kpa.db.models import Resume, ResumeParseStatus
from kpa.integrations.parser.base import (
    ParsedResume,
    ParserError,
    ResumeParser,
    TransientParserError,
)
from kpa.integrations.parser.library import LibraryResumeParser
from kpa.integrations.storage.local import LocalFileStorage
from kpa.workers.celery_app import celery_app, get_session_maker, settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_log = structlog.get_logger(__name__)


# --- Sync Celery entry point ---


@celery_app.task(
    name="kpa.parse_resume",
    bind=True,
    max_retries=3,
    autoretry_for=(TransientParserError,),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    acks_late=True,
)
def parse_resume(self, resume_id_str: str) -> None:  # type: ignore[no-untyped-def]
    """Sync entry. Wraps the async body in a fresh event loop."""
    asyncio.run(_parse_resume_async(UUID(resume_id_str)))


# --- Async body ---


async def _parse_resume_async(
    resume_id: UUID,
    *,
    sm: "async_sessionmaker[AsyncSession] | None" = None,
    storage: object | None = None,
    parser: ResumeParser | None = None,
) -> None:
    """Async body — split out for unit testing with injected fakes.

    Production callers (the Celery task) pass nothing; this resolves the real
    sessionmaker, LocalFileStorage, and LibraryResumeParser.
    """
    sm = sm or get_session_maker()
    storage = storage or LocalFileStorage(root=settings.storage_root)
    parser = parser or LibraryResumeParser()

    # --- Transaction 1: load + gate + mark parsing ---
    async with sm() as session:
        resume = await session.get(Resume, resume_id)
        if resume is None:
            _log.warning("parse.row-missing", resume_id=str(resume_id))
            return

        if resume.parse_status in {
            ResumeParseStatus.PARSED,
            ResumeParseStatus.FAILED,
            ResumeParseStatus.PARSING,
        }:
            _log.info(
                "parse.skip-non-pending",
                resume_id=str(resume_id),
                status=resume.parse_status.value,
            )
            return

        resume.parse_status = ResumeParseStatus.PARSING
        storage_key = resume.storage_key
        content_type = resume.content_type
        await session.commit()

    # --- Outside any DB txn: read + extract + parse ---
    try:
        content = await storage.read(storage_key)  # type: ignore[attr-defined]
        parsed: ParsedResume = await parser.parse(content=content, content_type=content_type)
    except ParserError as exc:
        await _mark_failed(sm, resume_id, reason=str(exc))
        return
    except TransientParserError:
        # Reraise unchanged so Celery autoretry fires. Row stays at 'parsing'.
        raise
    except Exception as exc:
        _log.exception("parse.unexpected", resume_id=str(resume_id))
        # Wrap so it hits the autoretry list, but cap by Celery's max_retries.
        raise TransientParserError(f"unexpected: {type(exc).__name__}") from exc

    # --- Transaction 3: re-load + verify + persist final ---
    async with sm() as session:
        resume = await session.get(Resume, resume_id)
        if resume is None or resume.parse_status != ResumeParseStatus.PARSING:
            _log.warning(
                "parse.row-mutated-mid-parse",
                resume_id=str(resume_id),
                current_status=resume.parse_status.value if resume else "missing",
            )
            return
        resume.parsed_json = parsed.model_dump(mode="json")
        resume.parse_status = ResumeParseStatus.PARSED
        resume.parse_error = None
        await session.commit()

    _log.info(
        "parse.complete",
        resume_id=str(resume_id),
        parser=parsed.parser_name,
        skills_count=len(parsed.skills),
    )


async def _mark_failed(
    sm: "async_sessionmaker[AsyncSession]",
    resume_id: UUID,
    *,
    reason: str,
) -> None:
    async with sm() as session:
        resume = await session.get(Resume, resume_id)
        if resume is None:
            return
        resume.parse_status = ResumeParseStatus.FAILED
        resume.parse_error = reason[:1000]
        await session.commit()
    _log.warning("parse.failed", resume_id=str(resume_id), reason=reason)
```

- [ ] **Step 4: Run the new tests**

```bash
uv run pytest tests/unit/test_parse_task.py -v -m integration
```

All 7 pass (parametrize unfolds `test_parse_idempotent_on_terminal_or_in_progress_status` into 3 cases).

- [ ] **Step 5: Lint + types + full pipeline**

```bash
uv run ruff check src/ tests/
uv run mypy
uv run pytest -v
```

All clean and green.

If mypy complains about `parse_resume` decorator (`@celery_app.task` returns a callable but type info is loose):
- The `# type: ignore[no-untyped-def]` comment on `def parse_resume(self, resume_id_str: str)` is intentional. Celery's decorator returns a generic Task subclass; bind=True passes `self`. The type stubs don't model this perfectly.

If mypy complains about `storage: object | None` losing the `.read` attribute:
- The `# type: ignore[attr-defined]` on the `storage.read(...)` call is the right escape. We can't import the Storage Protocol because then mypy chokes when tests pass `_FakeStorage` (structural typing works at runtime but mypy strict wants nominal). The escape is local + intentional.

If a test fails because the `kpa_test` integration database isn't running, see the README's Database section.

- [ ] **Step 6: Commit**

```bash
git add api/src/kpa/workers/tasks/__init__.py \
    api/src/kpa/workers/tasks/parse.py \
    api/tests/unit/test_parse_task.py
git commit -m "$(cat <<'EOF'
feat(api): add parse_resume task — 3-txn split, retry, idempotency

Sync Celery entry wraps _parse_resume_async via asyncio.run.

Three-transaction split:
- Txn 1: load row, gate on parse_status, mark parsing, commit. Short
  row lock only. Polling clients see the 'parsing' transition immediately.
- (no txn) Read bytes from storage, extract text, parser.parse(). Can take
  seconds; no row lock held.
- Txn 3: re-load row, verify still parsing (refuses to overwrite if status
  mutated externally), write parsed_json + status, commit.

Idempotency: skip if status is parsed/failed/parsing. ParserError marks
failed immediately (no retry). TransientParserError reraises so Celery
autoretry fires. Other unexpected exceptions are wrapped and retried up
to max_retries=3 with exponential backoff (2s → 4s → 8s, jittered).

Unit tests run the async body directly with injected fakes for storage
and parser, against the kpa_test Postgres. Covers happy path,
ParserError → failed, TransientParserError → reraise, idempotency on
each non-pending state, missing-row silent return.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Dispatch from upload route + broker-down resilience

**Files:**
- Modify: `api/src/kpa/routes/resumes.py`
- Create: `api/tests/integration/test_dispatch_resilient.py`

The POST handler enqueues `parse_resume.delay(...)` after the DB commit. Broker outages are logged but don't fail the upload (the row exists, the file is durable, an admin can replay later).

- [ ] **Step 1: Write the broker-down test FIRST**

Create `api/tests/integration/test_dispatch_resilient.py`:

```python
"""Integration test for upload-route resilience when the Celery broker is down."""

from __future__ import annotations

import io

import pytest
from fpdf import FPDF
from sqlalchemy import select

from kpa.db.models import Applicant, Resume, ResumeParseStatus, User, UserRole

pytestmark = pytest.mark.integration


def _tiny_pdf() -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(text="resume content")
    return bytes(pdf.output())


async def _make_applicant(session) -> str:
    user = User(email="dispatch@ex.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="Dispatch Test")
    session.add(applicant)
    await session.commit()
    return str(applicant.id)


async def test_upload_returns_201_even_if_broker_dispatch_raises(
    async_client,
    session,
    monkeypatch,
) -> None:
    """If parse_resume.delay() raises (broker down), upload still returns 201
    and the row exists with parse_status=pending."""
    from kpa.workers.tasks import parse as parse_module

    def _raise_broker_down(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr(parse_module.parse_resume, "delay", _raise_broker_down)

    applicant_id = await _make_applicant(session)
    pdf = _tiny_pdf()

    resp = await async_client.post(
        f"/v1/applicants/{applicant_id}/resumes",
        files={"file": ("cv.pdf", io.BytesIO(pdf), "application/pdf")},
    )

    assert resp.status_code == 201
    row = (
        await session.execute(
            select(Resume).where(Resume.applicant_id.in_([applicant_id]))
        )
    ).scalar_one()
    assert row.parse_status == ResumeParseStatus.PENDING
```

- [ ] **Step 2: Run, confirm it fails**

```bash
uv run pytest tests/integration/test_dispatch_resilient.py -v
```

Expected: test fails because the route hasn't been modified yet — `parse_resume.delay()` isn't called at all, so the monkeypatch never fires; but more importantly the test relies on the new behavior. It'll likely error with `ModuleNotFoundError: No module named 'kpa.workers.tasks.parse'` if Task 8 imports aren't visible yet, or pass trivially.

Actually for this to be a useful failing test, modify the route first, then verify the test fails because the broker-down path raises 500. But the simplest TDD order is: write test, then write impl, then test passes.

Run the test now; if it passes trivially (route doesn't call delay), that's OK — we'll see it stay green after Step 3.

- [ ] **Step 3: Modify the upload route**

Edit `api/src/kpa/routes/resumes.py`. Add an import near the top, alongside the existing imports:

```python
import structlog
from kpa.workers.tasks.parse import parse_resume
```

Add `_log` near the top of the module (after imports, before the router):

```python
_log = structlog.get_logger(__name__)
```

(If the file already has `_log` or `structlog`, don't duplicate — verify and skip.)

In `upload_resume`, find the line `await session.commit()`. Add directly after it:

```python
    # Dispatch async parse — broker outages MUST NOT fail the upload because
    # the resume row + file are already durable. Admin tooling can replay
    # pending rows after the broker recovers.
    try:
        parse_resume.delay(str(resume.id))
    except Exception as exc:
        _log.warning(
            "dispatch.broker-unavailable",
            resume_id=str(resume.id),
            error=type(exc).__name__,
        )
```

The existing `await session.refresh(resume)` and `return resume` stay below.

- [ ] **Step 4: Run the test, confirm green**

```bash
uv run pytest tests/integration/test_dispatch_resilient.py -v
```

Test passes. Upload returns 201; row stays `pending`.

- [ ] **Step 5: Existing route tests still green**

```bash
uv run pytest tests/integration/test_resumes_upload.py -v
```

All pass. (The route's behavior is unchanged on the happy path because eager mode runs the task inline — the existing tests either don't enable eager mode or do, and pass either way.)

- [ ] **Step 6: Lint + types**

```bash
uv run ruff check src/ tests/
uv run mypy
```

Clean.

- [ ] **Step 7: Commit**

```bash
git add api/src/kpa/routes/resumes.py api/tests/integration/test_dispatch_resilient.py
git commit -m "$(cat <<'EOF'
feat(api): dispatch parse_resume.delay() after upload commit

Triggers async parse from the POST /v1/applicants/{aid}/resumes
handler. Wrapped in try/except: a broker outage (Redis down,
connection refused) is logged as dispatch.broker-unavailable but
DOES NOT fail the upload — the resume row and file are durable,
admin tooling can replay pending rows after recovery.

Integration test confirms: even when parse_resume.delay raises a
ConnectionError, the POST returns 201 and the row exists with
parse_status=pending.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Integration pipeline tests (eager mode)

**Files:**
- Create: `api/tests/integration/test_parse_pipeline.py`

End-to-end: upload a tiny real PDF, run the parse task inline (via `task_always_eager`), poll the GET endpoint and assert the row transitions to `parsed` with a non-empty `parsed_json`.

- [ ] **Step 1: Write the tests**

Create `api/tests/integration/test_parse_pipeline.py`:

```python
"""Full upload → parse round trip via Celery eager mode."""

from __future__ import annotations

import io

import pytest
from fpdf import FPDF
from sqlalchemy import select

from kpa.db.models import Applicant, Resume, ResumeParseStatus, User, UserRole

pytestmark = pytest.mark.integration


def _tiny_pdf_with(text_lines: list[str]) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in text_lines:
        pdf.cell(text=line, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


async def _make_applicant(session, *, email: str = "pipeline@ex.com") -> str:
    user = User(email=email, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(user_id=user.id, full_name="Pipeline Test")
    session.add(applicant)
    await session.commit()
    return str(applicant.id)


async def test_upload_then_parse_populates_parsed_json(
    async_client,
    session,
    monkeypatch,
) -> None:
    """Eager mode: .delay() runs the task body inline; by the time the response
    returns, the row is already parsed."""
    monkeypatch.setenv("KPA_CELERY_TASK_ALWAYS_EAGER", "true")
    # Reload settings so the celery_app picks up the eager flag.
    import importlib

    from kpa.workers import celery_app as celery_module

    importlib.reload(celery_module)

    applicant_id = await _make_applicant(session)
    pdf = _tiny_pdf_with(
        [
            "John Doe",
            "Email: john.doe@example.com",
            "Phone: +91-98765-43210",
            "Skills: Python, FastAPI, Postgres",
        ]
    )

    resp = await async_client.post(
        f"/v1/applicants/{applicant_id}/resumes",
        files={"file": ("cv.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    assert resp.status_code == 201
    resume_id = resp.json()["id"]

    # Re-query through the session — eager mode commits via the worker's own
    # sessionmaker, NOT the test's shared session. We need a fresh read.
    await session.commit()  # release any open transaction
    row = (await session.execute(select(Resume).where(Resume.id == resume_id))).scalar_one()
    assert row.parse_status == ResumeParseStatus.PARSED, (
        f"expected parsed, got {row.parse_status}; parse_error={row.parse_error}"
    )
    assert row.parsed_json is not None
    assert row.parsed_json["parser_name"] == "library.v1"
    assert row.parsed_json["schema_version"] == 1
    assert row.parsed_json["email"] == "john.doe@example.com"
    assert "python" in row.parsed_json["skills"]
    assert "fastapi" in row.parsed_json["skills"]


async def test_upload_of_unsupported_blob_marks_failed(
    async_client,
    session,
    monkeypatch,
) -> None:
    """Upload a .docx content-type with random bytes; parser raises
    ParserError('docx_read_error'), task marks the row failed."""
    monkeypatch.setenv("KPA_CELERY_TASK_ALWAYS_EAGER", "true")
    import importlib

    from kpa.workers import celery_app as celery_module

    importlib.reload(celery_module)

    applicant_id = await _make_applicant(session, email="failed@ex.com")
    junk = b"\x00" * 200

    resp = await async_client.post(
        f"/v1/applicants/{applicant_id}/resumes",
        files={
            "file": (
                "cv.docx",
                io.BytesIO(junk),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert resp.status_code == 201
    resume_id = resp.json()["id"]

    await session.commit()
    row = (await session.execute(select(Resume).where(Resume.id == resume_id))).scalar_one()
    assert row.parse_status == ResumeParseStatus.FAILED
    assert row.parse_error == "docx_read_error"
```

- [ ] **Step 2: Run the new tests**

```bash
uv run pytest tests/integration/test_parse_pipeline.py -v
```

Both pass.

If `test_upload_then_parse_populates_parsed_json` shows `parse_status=pending` instead of `parsed`: the `importlib.reload` of `celery_app` may have created a second Celery app instance that the route's task import still doesn't see. Workaround: monkeypatch the `task_always_eager` attribute on the existing celery_app directly:

```python
    from kpa.workers.celery_app import celery_app
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)
```

Use this if the reload path proves flaky.

If the eager-mode task body's commit isn't visible to the test session: the integration conftest uses a savepoint-isolated session; the worker creates its own session/connection so writes are committed to the DB but the test's session has its own snapshot. `await session.commit()` then re-querying via `session.execute` should pick up the new state. If not, switch to a direct query via `migrated_db`:

```python
    from sqlalchemy.ext.asyncio import create_async_engine
    import os
    url = os.environ.get("KPA_TEST_DB_URL", "postgresql+asyncpg://kpa:kpa@localhost:5432/kpa_test")
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        row = (await conn.execute(select(Resume).where(Resume.id == resume_id))).first()
        # ... assertions
    await engine.dispose()
```

- [ ] **Step 3: Full suite green**

```bash
uv run pytest -v
```

All passing. Expected total: 28 baseline + 12 new unit + 3 new integration = ~43 tests.

- [ ] **Step 4: Lint + types**

```bash
uv run ruff check src/ tests/
uv run mypy
```

Clean.

- [ ] **Step 5: Commit**

```bash
git add api/tests/integration/test_parse_pipeline.py
git commit -m "$(cat <<'EOF'
test(api): full upload → parse pipeline (eager mode)

Two end-to-end tests via Celery eager mode:
- Happy path: POST a real (fpdf2-generated) PDF, verify the resume
  row transitions to parsed with parser_name=library.v1,
  schema_version=1, and the expected email + skills extracted.
- Failure path: POST junk bytes with a .docx content type, verify
  the row transitions to failed with parse_error='docx_read_error'.

Eager mode (KPA_CELERY_TASK_ALWAYS_EAGER=true) runs the task body
inline in the calling thread — no broker, no worker process, but
the real parser, real storage, real DB writes are exercised.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Docs — README + spec §13 + §11.1 updates

**Files:**
- Modify: `api/README.md`
- Modify: `IMPLEMENTATION_SPEC.md`

Document Redis setup, the new env vars, and how to run the worker. Update the spec so the Celery-at-P1 decision is reflected in the source-of-truth.

- [ ] **Step 1: Append Redis setup to the README**

Edit `api/README.md`. After the existing **Database** section (look for `## Database` heading), add a new section:

```markdown
## Redis (for the parse worker)

The resume parse pipeline runs on Celery + Redis. Local dev uses Homebrew Redis on the default port.

### First-time setup

\`\`\`bash
brew install redis
brew services start redis
\`\`\`

Verify it's up:

\`\`\`bash
redis-cli ping     # → PONG
\`\`\`

The connection string lives in `.env`:

\`\`\`
KPA_REDIS_URL=redis://localhost:6379/0
\`\`\`

### Run the parse worker

In a second terminal (uvicorn keeps running in the first):

\`\`\`bash
cd api
uv run --env-file=.env celery -A kpa.workers.celery_app worker \\
    --pool=solo --concurrency=1 -Q parse --loglevel=info
\`\`\`

- `--pool=solo`: single-concurrency. The MVP pattern; switch to `--pool=prefork` later when load justifies parallelism.
- `-Q parse`: only consume from the `parse` queue. Future `embed`/`score`/`notify` queues land in their own plans.

Upload a resume in the first terminal; the worker logs `parse.complete` when it's done. Poll `GET /v1/applicants/{aid}/resumes/{rid}` to see `parse_status` transition.

### Skipping the worker for tests

Tests use Celery eager mode (set via `KPA_CELERY_TASK_ALWAYS_EAGER=true` in test fixtures) so `.delay()` runs the task body inline — no Redis required during `pytest`. Production never sets this flag.
```

- [ ] **Step 2: Add new env vars to the Configuration table**

Find the **Configuration** section's env-var table and append two rows:

```markdown
| `KPA_REDIS_URL`    | yes      | —       | Redis connection string (`redis://` or `rediss://`). Required for Celery broker. |
| `KPA_CELERY_TASK_ALWAYS_EAGER` | no | `false` | When true, Celery tasks run synchronously in-process. Tests only. |
```

- [ ] **Step 3: Update Project layout**

Find the `## Project layout` section and update the `src/kpa/` tree to include the new packages. Add inside the tree:

```
│   ├── workers/
│   │   ├── celery_app.py     # Celery instance + per-worker engine lifecycle
│   │   └── tasks/
│   │       └── parse.py       # parse_resume — 3-txn split, retry, idempotency
│   ├── integrations/
│   │   ├── storage/          # Storage protocol + LocalFileStorage
│   │   └── parser/
│   │       ├── base.py        # ResumeParser Protocol + ParsedResume schema
│   │       ├── text.py        # PDF (pypdf+pdfminer) + DOCX extraction
│   │       ├── library.py     # LibraryResumeParser — regex + keyword impl
│   │       └── skills_dict.py # Curated skill keyword list
```

(Replace the existing `│   ├── integrations/` block; preserve the rest.)

- [ ] **Step 4: Update IMPLEMENTATION_SPEC.md §13 + §11.1**

Edit `IMPLEMENTATION_SPEC.md`.

**§11.1 MVP runtime** — find the line:

```
  - Redis: deferred to the plan that introduces Celery (P3-era); until then the API runs synchronously where possible.
```

Replace with:

```
  - Redis: introduced at P1 by the resume parse worker plan (was originally planned for P3; advanced because §6.1 needs async parse). Local Redis via Homebrew (`brew install redis && brew services start redis`). The Celery broker + result backend both point at it.
```

**§13 MVP build sequence** — find the **P3 — Notifications + applications** bullet:

```
- First introduction of Redis (locally via Homebrew) + Celery — still no Docker required for dev.
```

Replace with:

```
- Notification-side Celery queues (`notify`, `dsr`) added — Redis + Celery already in the stack from the P1 parse worker plan.
```

**§13 P1 — Resume parse + embed** — find the line:

```
- Local-filesystem upload first; S3 presigned upload behind the same `storage` interface, switched on by env. Parse worker, embedding worker, status surfacing.
```

Replace with:

```
- Local-filesystem upload first; S3 presigned upload behind the same `storage` interface, switched on by env. Parse worker landed (Celery + Redis, library/regex parser); embedding worker + status push remain.
```

- [ ] **Step 5: Lint stays clean (no code changes here)**

```bash
uv run ruff check src/ tests/
```

Clean.

- [ ] **Step 6: Commit**

```bash
git add api/README.md IMPLEMENTATION_SPEC.md
git commit -m "$(cat <<'EOF'
docs(api): document Redis + parse worker; update spec §13 + §11.1

README adds:
- Redis Homebrew install + verification
- How to run the parse worker (`celery -A kpa.workers.celery_app
  worker --pool=solo -Q parse`)
- KPA_REDIS_URL + KPA_CELERY_TASK_ALWAYS_EAGER in the config table
- Updated project layout with workers/ + integrations/parser/

IMPLEMENTATION_SPEC.md:
- §11.1: Redis is no longer "deferred to P3-era"; it landed at P1.
- §13 P1: parse worker shipped; embedding worker + status push remain
- §13 P3: Celery is no longer "first introduced here" — just adds
  notify/dsr queues to the existing stack.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final check

After all tasks land, from `api/`:

```bash
# Lint + types
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy

# Tests (unit + integration both)
uv run pytest -v -m "not integration"
uv run pytest -v -m integration
uv run pytest -v
```

All commands exit 0. Expected total: **~43 tests** (28 baseline + 12 new unit + 3 new integration).

Then verify the full pipeline manually with Redis running:

```bash
# Terminal 1 — Redis is already started via brew services
# Terminal 2 — API
cd api
uv run --env-file=.env uvicorn kpa.main:app --reload --port 8000

# Terminal 3 — worker
cd api
uv run --env-file=.env celery -A kpa.workers.celery_app worker \
    --pool=solo --concurrency=1 -Q parse --loglevel=info

# Terminal 4 — upload + poll
# (Create an applicant via psql first — see README's "Resume uploads" section)
APPLICANT_ID=<from psql>
curl -s -X POST "http://127.0.0.1:8000/v1/applicants/$APPLICANT_ID/resumes" \
    -F "file=@/path/to/cv.pdf" | python -m json.tool
# Returns 201 with resume.id and parse_status=pending

RESUME_ID=<from above>
# Poll until status is parsed/failed
while true; do
    curl -s "http://127.0.0.1:8000/v1/applicants/$APPLICANT_ID/resumes/$RESUME_ID" \
        | python -c "import json, sys; d=json.load(sys.stdin); print(d['parse_status'])"
    sleep 1
done
```

The worker terminal shows `parse.complete` log lines. The polling loop transitions from `pending` → `parsing` → `parsed` (with the library parser this happens in well under a second for a small PDF).

Then push the branch and open a PR against `feat/p0-db-layer-and-user-model` (already merged to itself upstream — GitHub will auto-target appropriately).

---

## Out of scope (intentionally — handled by later plans)

- **Embedding worker** — separate plan, blocked on spec §14 #2 (embedding provider + dimension).
- **Match-trigger worker** — blocked on jobs schema landing.
- **LLM-backed `ResumeParser` impl** — Protocol ships here, impl deferred behind §14 #1 (LLM provider) + §9.2 (DPDP residency).
- **`.doc` legacy binary parsing** — raises `ParserError("doc_legacy_not_supported")` until antiword/LibreOffice deps land.
- **OCR for image-only PDFs** — raises `ParserError("no_text_extracted")`.
- **Magic-byte content-type verification + ClamAV scan** — already deferred by the P1.0 plan.
- **Admin "replay failed parse" tooling** — `failed` rows accumulate until P4-era admin lands.
- **FCM push on parse completion** — polling only; spec §6.1 step 4's push lands with the P3 notifications plan.
- **Parse F1 gold-dataset CI gate** — BRD ≥ 0.90 target (§7) applies to the LLM parser. Library parser's quality is informational only.
- **`/v1/applicants/me/resumes` alias** — independent small follow-up (deferred from the P1.0 plan and the auth plan).
- **Celery `--pool=prefork` + per-process engine tuning** — P5 hardening; the worker_process_init signal already supports it.
- **`/health`/`/ready` for the worker process** — P3 observability item.
- **Schema-version migration tooling** — `parsed_json.schema_version=1`. A v2 bump owns its own re-parse plan.

---

## Spec traceback

This plan implements the design at `docs/superpowers/specs/2026-05-18-resume-parse-worker-design.md`. Spec sections → task mapping:

- **Architecture overview** → distributed across all tasks.
- **Spec deltas (§13, §11.1, §6.1)** → Task 11.
- **Parser interface + ParsedResume schema** → Task 3.
- **Library parser impl** → Task 4 (skills dict) + Task 6 (regex impl).
- **Text extraction (pypdf + pdfminer + python-docx)** → Task 5.
- **Worker mechanics (Celery app, per-worker engine)** → Task 7.
- **3-txn split, retry, idempotency** → Task 8.
- **Dispatch from upload route + broker-down resilience** → Task 9.
- **Eager-mode integration tests** → Task 10.
- **Settings + env (KPA_REDIS_URL, KPA_CELERY_TASK_ALWAYS_EAGER)** → Task 2.
- **New dependencies** → Task 1.
- **Security posture, observability** → distributed (Task 8 owns the log events; Task 1 + 7 own the deps).
