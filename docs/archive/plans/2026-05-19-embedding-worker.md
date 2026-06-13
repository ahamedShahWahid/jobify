# Embedding worker — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `embed_applicant` Celery task that reads `parse_status=parsed` rows, computes a 1536-dim Gemini embedding over the canonicalized applicant profile, and persists it in a new `applicant_embeddings` table. Dispatched fire-and-forget from `parse_resume`'s Txn3.

**Architecture:** New `kpa.integrations.embeddings` package (provider interface + Gemini impl + canonicalize helper). New `ApplicantEmbedding` model + Alembic 0004. New `kpa.workers.tasks.embed` module with a 3-transaction-split worker mirroring `parse_resume`'s shape. Dispatch wired into `parse_resume` Txn3 with the same broad-except discipline as the upload route. Three new env vars (`KPA_GEMINI_API_KEY`, `KPA_EMBEDDING_MODEL`, `KPA_EMBEDDING_DIM`). New `embed` Celery queue.

**Tech Stack:** Gemini Developer API (`google-genai` SDK), pgvector, SQLAlchemy 2.x async, Alembic, Celery, pytest + httpx.

**Source-of-truth spec:** `docs/superpowers/specs/2026-05-19-embedding-worker-design.md`.

---

## File structure

| File | Action | Responsibility |
|---|---|---|
| `api/pyproject.toml` + `uv.lock` | Modify | Add `pgvector` and `google-genai` deps. |
| `api/src/kpa/integrations/embeddings/__init__.py` | Create | Public re-exports. |
| `api/src/kpa/integrations/embeddings/base.py` | Create | `EmbeddingTask` enum, `EmbeddingResult` dataclass, `EmbeddingProvider` Protocol, `EmbeddingProviderError` + `TransientEmbeddingError`. |
| `api/src/kpa/integrations/embeddings/canonicalize.py` | Create | `canonicalize_profile(parsed, *, full_name) -> (text, sha256_hex)`. Deterministic. |
| `api/src/kpa/integrations/embeddings/gemini.py` | Create | `GeminiEmbeddingProvider` impl. Prompt-prefix task formatting. Maps Gemini SDK errors → embeddings errors. |
| `api/src/kpa/db/models.py` | Modify | Add `ApplicantEmbedding` model. |
| `api/src/kpa/db/migrations/versions/0004_applicant_embeddings.py` | Create | `CREATE EXTENSION vector`, table create, HNSW index. |
| `api/src/kpa/settings.py` | Modify | `KPA_GEMINI_API_KEY` (required), `KPA_EMBEDDING_MODEL` (default `gemini-embedding-2`), `KPA_EMBEDDING_DIM` (default 1536). |
| `api/.env.example` | Modify | Document the three new vars. |
| `api/src/kpa/workers/celery_app.py` | Modify | Register `embed` queue; provider factory on `app.state`. |
| `api/src/kpa/workers/tasks/embed.py` | Create | `embed_applicant` task + `_embed_applicant_async` + `_load_latest_parsed_resume` helper. 3-txn split, mirrors `parse.py`. |
| `api/src/kpa/workers/tasks/parse.py` | Modify | Dispatch `embed_applicant.delay()` from Txn3 post-commit, fire-and-forget. |
| `api/tests/unit/test_canonicalize.py` | Create | Determinism + field-order invariance + skill normalization. |
| `api/tests/unit/test_gemini_provider.py` | Create | Prompt formatting per task; HTTP error → error-type mapping. Uses a mock SDK client. |
| `api/tests/unit/test_settings.py` | Modify | Add cases for the three new vars (required, default, validation). |
| `api/tests/integration/test_embed_worker.py` | Create | Happy path, idempotency, stale-content abort, dispatch resilience. |
| `api/tests/integration/test_parse_pipeline.py` | Modify | One added assertion: `applicant_embeddings` row exists after parse. |
| `api/tests/integration/conftest.py` | Modify | Inject `KPA_GEMINI_API_KEY="test"` + `app.dependency_overrides[get_embedding_provider]` returning a fake. |
| `api/README.md` | Modify | Env vars table, worker command (`-Q parse,embed`). |
| `CLAUDE.md` | Modify | New subsection in §Architecture: "Embedding worker (Gemini)" — same density as the parse-worker section. |
| `IMPLEMENTATION_SPEC.md` | Modify | §5 vector dim; §6.1 step 5 clarification; §7 task-encoding note. |

Total touches: 21 files (10 new, 11 modified). Estimated commits: 6.

---

## Background the engineer needs

- The provider interface deliberately wraps the prompt-prefix formatting so call sites pass `EmbeddingTask.DOCUMENT` and never see `title: … | text: …`. A future Voyage / Cohere swap is a single-file change inside `integrations/embeddings/`.
- `gemini-embedding-2` does NOT accept the `task_type` param — that was a `gemini-embedding-001` thing. Don't add it back.
- `pgvector.sqlalchemy.Vector` is the SQLAlchemy column type for the embedding. Requires the `pgvector` Python package AND the Postgres `vector` extension. The migration runs `CREATE EXTENSION` first.
- The `_log.warning("dispatch.failed", exc_info=True)` shape at `routes/resumes.py:144-161` is canonical for fire-and-forget dispatch — match it exactly for `_log.warning("embed.dispatch-failed", ...)`.
- `parse_resume` is `acks_late=True`. The embed task should match — same broker semantics.
- Integration tests require `CREATE EXTENSION vector` privileges on `kpa_test`. The Homebrew Postgres role `kpa` already has `CREATEDB` (per README) but not necessarily extension-create. The migration will run as the connection role; if extension-create fails, the readme needs an updated psql line.
- The `concurrent_async_client` fixture truncates `kpa.resumes`, `kpa.refresh_tokens`, etc. — when this slice lands, `kpa.applicant_embeddings` joins that list (FK CASCADE on applicant_id handles it implicitly, but explicit truncation keeps the test self-contained).
- For tests, the Gemini provider is overridden via `app.dependency_overrides[get_embedding_provider]`. The fake returns a deterministic 1536-dim vector derived from `hash(text) % 1.0` so tests can assert on identity without flakiness.

---

## Tasks

### Task 1: Create the feature branch

- [ ] **Step 1:** Verify `main` is clean and at the post-PR-#7 merge.
```bash
git status                                      # working tree clean (excluding the two new doc files)
git rev-parse --abbrev-ref HEAD                 # main
git log -1 --oneline                            # should show the PR #7 merge commit
```

- [ ] **Step 2:** Branch off.
```bash
git checkout -b feat/p1.3-embedding-worker
```

---

### Task 2: Add `pgvector` and `google-genai` dependencies

**Files:** `api/pyproject.toml`, `api/uv.lock`

- [ ] **Step 1:** In `api/pyproject.toml`, add to `dependencies = [...]`:
  - `"pgvector>=0.3.0,<0.4"`
  - `"google-genai>=1.0,<2"` (the official Google GenAI SDK; supersedes `google-generativeai`)

- [ ] **Step 2:** Sync + commit.
```bash
cd api
uv sync
git add pyproject.toml uv.lock
git commit -m "build(api): add pgvector + google-genai deps for embedding worker"
```

---

### Task 3: Add the embeddings module — interface, canonicalize, Gemini impl, unit tests

**Files (create):** `integrations/embeddings/__init__.py`, `base.py`, `canonicalize.py`, `gemini.py`. **Unit tests:** `test_canonicalize.py`, `test_gemini_provider.py`.

- [ ] **Step 1: `base.py`** — types and Protocol.

```python
"""Embedding provider interface.

Task is encoded via prompt-prefix at the impl layer; call sites pass the
``EmbeddingTask`` enum and the impl formats accordingly. Keeps a future
Voyage/Cohere swap a single-file change.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class EmbeddingTask(StrEnum):
    DOCUMENT = "document"   # applicant profile (or job description, in P2)
    QUERY = "query"         # recruiter-side query (in P2)


@dataclass(frozen=True)
class EmbeddingResult:
    values: list[float]
    model_name: str
    input_tokens: int


class EmbeddingProviderError(Exception):
    """Permanent failure — bad input, malformed response, etc. No retry."""


class TransientEmbeddingError(Exception):
    """Transient failure — rate limit, 5xx, network blip. Celery autoretries."""


class EmbeddingProvider(Protocol):
    async def encode(
        self,
        *,
        text: str,
        task: EmbeddingTask,
        title: str | None = None,
    ) -> EmbeddingResult: ...
```

- [ ] **Step 2: `canonicalize.py`** — deterministic profile text + hash.

```python
"""Canonicalize a parsed resume to a deterministic text representation.

Stable ordering and normalization is critical: the sha256 of the output is the
idempotency key on ``applicant_embeddings.canonicalized_text_hash``. A reordering
of skills or a different rendering of dates must NOT change the hash.
"""
from __future__ import annotations

import hashlib
from kpa.integrations.parser.base import ParsedResume


def canonicalize_profile(parsed: ParsedResume, *, full_name: str) -> tuple[str, str]:
    skills = sorted({s.strip().lower() for s in parsed.skills if s.strip()})
    experience_lines = sorted(
        f"- {r.title} @ {r.company} ({r.start or '?'}–{r.end or 'present'}): "
        f"{(r.description or '').strip()}"
        for r in parsed.experience
    )
    education_lines = sorted(
        f"- {e.degree}, {e.institution} ({e.start or '?'}–{e.end or '?'})"
        for e in parsed.education
    )
    certifications = sorted({c.strip() for c in parsed.certifications if c.strip()})

    lines = [
        full_name.strip(),
        "Skills: " + ", ".join(skills),
        f"Experience: {parsed.years_experience or 0}y total",
        *experience_lines,
        "Education:",
        *education_lines,
        "Certifications: " + ", ".join(certifications),
    ]
    text = "\n".join(lines)
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()
```

> Engineer note: if `ParsedResume` doesn't yet have all these fields exposed (`experience`, `education`, `certifications`, `years_experience`), check `integrations/parser/base.py` for the current shape and adapt — DON'T fabricate fields the parser doesn't produce. The current library parser produces a subset; the canonicalizer should gracefully handle missing fields rather than assume they're there.

- [ ] **Step 3: `gemini.py`** — `GeminiEmbeddingProvider` impl.

```python
"""Gemini Developer API embedding provider — gemini-embedding-2 by default.

Task is encoded via prompt prefix (gemini-embedding-2 does NOT accept the
``task_type`` parameter; that was a gemini-embedding-001 thing).
"""
from __future__ import annotations

import structlog
from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError

from kpa.integrations.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingResult,
    EmbeddingTask,
    TransientEmbeddingError,
)

_log = structlog.get_logger(__name__)


class GeminiEmbeddingProvider(EmbeddingProvider):
    def __init__(self, *, api_key: str, model: str, output_dim: int) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._output_dim = output_dim

    async def encode(
        self,
        *,
        text: str,
        task: EmbeddingTask,
        title: str | None = None,
    ) -> EmbeddingResult:
        if task is EmbeddingTask.DOCUMENT:
            content = f"title: {title or 'none'} | text: {text}"
        elif task is EmbeddingTask.QUERY:
            content = f"task: search result | query: {text}"
        else:
            raise EmbeddingProviderError(f"unsupported task: {task}")

        try:
            resp = await self._client.aio.models.embed_content(
                model=self._model,
                contents=[content],
                config=types.EmbedContentConfig(output_dimensionality=self._output_dim),
            )
        except ServerError as exc:           # 5xx
            raise TransientEmbeddingError(str(exc)) from exc
        except ClientError as exc:
            # 429 is transient; 4xx other than 429 is permanent.
            if getattr(exc, "code", None) == 429:
                raise TransientEmbeddingError(str(exc)) from exc
            raise EmbeddingProviderError(str(exc)) from exc
        except APIError as exc:
            raise EmbeddingProviderError(str(exc)) from exc

        if not resp.embeddings or not resp.embeddings[0].values:
            raise EmbeddingProviderError("empty embedding response")
        emb = resp.embeddings[0]
        if len(emb.values) != self._output_dim:
            raise EmbeddingProviderError(
                f"dim mismatch: got {len(emb.values)} expected {self._output_dim}"
            )
        return EmbeddingResult(
            values=list(emb.values),
            model_name=self._model,
            input_tokens=getattr(emb, "input_tokens", 0) or 0,
        )
```

> Engineer note: verify the exact `google-genai` SDK exception names against the installed version. The pattern (5xx→transient, 429→transient, other 4xx→permanent) is what matters; adjust import paths if the SDK uses different exception classes than `ServerError`/`ClientError`/`APIError`. Update via `uv run python -c "from google.genai import errors; print(dir(errors))"`.

- [ ] **Step 4: `__init__.py`** — re-exports.

```python
from kpa.integrations.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingResult,
    EmbeddingTask,
    TransientEmbeddingError,
)
from kpa.integrations.embeddings.canonicalize import canonicalize_profile
from kpa.integrations.embeddings.gemini import GeminiEmbeddingProvider

__all__ = [
    "EmbeddingProvider", "EmbeddingProviderError", "EmbeddingResult",
    "EmbeddingTask", "TransientEmbeddingError",
    "canonicalize_profile", "GeminiEmbeddingProvider",
]
```

- [ ] **Step 5: Unit tests.**

`test_canonicalize.py`:
- `test_same_parsed_resume_yields_identical_text_and_hash` — call twice on the same input, assert exact equality.
- `test_skill_reordering_does_not_change_hash` — same skills in different order produce same hash.
- `test_skill_case_normalized` — `Python` and `python` collapse to one entry in the canonical text.
- `test_missing_optional_fields_handled` — empty certifications / education / experience produce stable output without crashing.

`test_gemini_provider.py` (mock the SDK client via `unittest.mock.AsyncMock`):
- `test_document_task_formats_with_title_prefix` — assert the `contents` arg matches `title: {full_name} | text: {text}`.
- `test_query_task_formats_with_task_prefix` — assert `contents` matches `task: search result | query: {text}`.
- `test_5xx_maps_to_transient_error` — make the mock raise `ServerError`; expect `TransientEmbeddingError`.
- `test_429_maps_to_transient_error` — `ClientError` with code 429.
- `test_other_4xx_maps_to_permanent_error` — `ClientError` with code 400.
- `test_dim_mismatch_is_permanent_error` — mock returns 768 values when dim=1536; expect `EmbeddingProviderError`.

Run them:
```bash
uv run pytest -v tests/unit/test_canonicalize.py tests/unit/test_gemini_provider.py
```

- [ ] **Step 6:** Commit.
```bash
git add api/src/kpa/integrations/embeddings/ api/tests/unit/test_canonicalize.py api/tests/unit/test_gemini_provider.py
git commit -m "feat(api): add embeddings module — provider interface + Gemini impl + canonicalize"
```

---

### Task 4: Add `ApplicantEmbedding` model + migration 0004

**Files:** `db/models.py` (modify), `db/migrations/versions/0004_applicant_embeddings.py` (create).

- [ ] **Step 1:** In `db/models.py`, add (after `Resume`, before `OAuthProvider`):

```python
from pgvector.sqlalchemy import Vector  # at top with the other SQLAlchemy imports


class ApplicantEmbedding(Base):
    """One current vector per applicant. Re-embed UPSERTs in place."""

    __tablename__ = "applicant_embeddings"

    id: Mapped[UuidPK]
    applicant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kpa.applicants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    canonicalized_text_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    deleted_at: Mapped[DeletedAt]
```

- [ ] **Step 2:** Generate migration scaffold then hand-edit:
```bash
cd api
uv run alembic revision -m "applicant_embeddings"
```

Replace the body of the generated `0004_applicant_embeddings.py`:

```python
"""applicant_embeddings

Revision ID: 0004
Revises: 0003
Create Date: ...
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "applicant_embeddings",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("applicant_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("kpa.applicants.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("model_name", sa.String(64), nullable=False),
        sa.Column("canonicalized_text_hash", sa.CHAR(64), nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="kpa",
    )
    op.execute(
        "CREATE INDEX ix_applicant_embeddings_hnsw "
        "ON kpa.applicant_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS kpa.ix_applicant_embeddings_hnsw")
    op.drop_table("applicant_embeddings", schema="kpa")
    # Intentionally NOT dropping the vector extension — other tables in P2 (job_embeddings) will need it.
```

- [ ] **Step 3:** Test the migration cleanly applies + downgrades:
```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```
If `CREATE EXTENSION vector` fails for permissions, run as superuser:
```bash
psql -d postgres -c "CREATE EXTENSION vector;" -d kpa
psql -d postgres -c "CREATE EXTENSION vector;" -d kpa_test
```
And note in README that `pgvector` must be installed at the OS level (`brew install pgvector`).

- [ ] **Step 4:** Commit.
```bash
git add api/src/kpa/db/models.py api/src/kpa/db/migrations/versions/0004_applicant_embeddings.py
git commit -m "feat(api): ApplicantEmbedding model + migration 0004 (pgvector + HNSW)"
```

---

### Task 5: Three new env vars in `Settings`

**Files:** `settings.py`, `.env.example`, `tests/unit/test_settings.py`, `README.md` (env vars table).

- [ ] **Step 1:** In `settings.py`, add:

```python
gemini_api_key: SecretStr  # required; no default
embedding_model: str = "gemini-embedding-2"
embedding_dim: int = 1536
```

Validation: `embedding_dim` must be in `{128, 256, 512, 768, 1024, 1536, 3072}` (Matryoshka recommended set per Gemini docs); otherwise raise via a `model_validator`.

- [ ] **Step 2:** Update `.env.example`:
```
KPA_GEMINI_API_KEY=changeme
KPA_EMBEDDING_MODEL=gemini-embedding-2
KPA_EMBEDDING_DIM=1536
```

- [ ] **Step 3:** Update `api/README.md` env-vars table — add three rows.

- [ ] **Step 4:** Unit tests for new validation cases.

- [ ] **Step 5:** Update `tests/integration/conftest.py` and `tests/conftest.py` to inject `KPA_GEMINI_API_KEY="test-key"` everywhere `KPA_JWT_SECRET="x" * 32` is set (4 locations including `pipeline_client` and `concurrent_async_client`).

- [ ] **Step 6:** Commit.
```bash
git add api/src/kpa/settings.py api/.env.example api/tests/unit/test_settings.py api/tests/conftest.py api/tests/integration/conftest.py api/README.md
git commit -m "feat(api): add KPA_GEMINI_API_KEY/EMBEDDING_MODEL/EMBEDDING_DIM settings"
```

---

### Task 6: `embed_applicant` task with 3-txn split

**Files:** `workers/tasks/embed.py` (create), `workers/celery_app.py` (modify).

- [ ] **Step 1:** Register the `embed` queue in `celery_app.py`. Most likely the current config has `task_default_queue = "parse"` or similar; this becomes an explicit per-task route. Verify the current shape before editing.

Add (or extend) the route map:
```python
task_routes={
    "kpa.parse_resume": {"queue": "parse"},
    "kpa.embed_applicant": {"queue": "embed"},
}
```

Also extend `get_session_maker()` to be reusable, or add `get_embedding_provider()` if a similar lazy-singleton pattern is appropriate:

```python
_embedding_provider: GeminiEmbeddingProvider | None = None

def get_embedding_provider() -> GeminiEmbeddingProvider:
    global _embedding_provider
    if _embedding_provider is None:
        _embedding_provider = GeminiEmbeddingProvider(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.embedding_model,
            output_dim=settings.embedding_dim,
        )
    return _embedding_provider
```

- [ ] **Step 2:** Create `embed.py`. Mirror the shape of `parse.py`:

```python
"""embed_applicant task — read latest parsed resume, embed, upsert."""
from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import func

from kpa.db.models import Applicant, ApplicantEmbedding, Resume, ResumeParseStatus
from kpa.integrations.embeddings import (
    EmbeddingProvider, EmbeddingProviderError, EmbeddingTask,
    TransientEmbeddingError, canonicalize_profile,
)
from kpa.integrations.parser.base import ParsedResume
from kpa.workers.celery_app import celery_app, get_embedding_provider, get_session_maker

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_log = structlog.get_logger(__name__)


@celery_app.task(  # type: ignore[untyped-decorator]
    name="kpa.embed_applicant",
    bind=True,
    max_retries=3,
    autoretry_for=(TransientEmbeddingError,),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    acks_late=True,
)
def embed_applicant(self, applicant_id_str: str) -> None:  # type: ignore[no-untyped-def]
    """Same eager-mode thread-hop pattern as parse_resume."""
    def _run(coro_factory: Callable[[], Coroutine[Any, Any, None]]) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(asyncio.run, coro_factory())
                fut.result()
        else:
            asyncio.run(coro_factory())

    _run(lambda: _embed_applicant_async(UUID(applicant_id_str)))


async def _embed_applicant_async(
    applicant_id: UUID,
    *,
    sm: async_sessionmaker[AsyncSession] | None = None,
    provider: EmbeddingProvider | None = None,
) -> None:
    sm = sm or get_session_maker()
    provider = provider or get_embedding_provider()

    # Txn 1: gate
    async with sm() as session:
        applicant = await session.get(Applicant, applicant_id)
        if applicant is None or applicant.deleted_at is not None:
            _log.warning("embed.applicant-missing", applicant_id=str(applicant_id))
            return
        latest = (await session.execute(
            select(Resume)
            .where(
                Resume.applicant_id == applicant_id,
                Resume.parse_status == ResumeParseStatus.PARSED,
                Resume.deleted_at.is_(None),
            )
            .order_by(Resume.created_at.desc())
            .limit(1)
        )).scalar_one_or_none()
        if latest is None or latest.parsed_json is None:
            _log.info("embed.no-parsed-resume", applicant_id=str(applicant_id))
            return
        parsed = ParsedResume.model_validate(latest.parsed_json)
        text, content_hash = canonicalize_profile(parsed, full_name=applicant.full_name)
        existing = (await session.execute(
            select(ApplicantEmbedding).where(ApplicantEmbedding.applicant_id == applicant_id)
        )).scalar_one_or_none()
        if existing is not None and existing.canonicalized_text_hash == content_hash:
            _log.info("embed.idempotent-skip", applicant_id=str(applicant_id))
            return
        title = applicant.full_name

    # Txn 2: no DB. Errors propagate per the autoretry config.
    try:
        result = await provider.encode(text=text, task=EmbeddingTask.DOCUMENT, title=title)
    except EmbeddingProviderError as exc:
        _log.error("embed.permanent-failure", applicant_id=str(applicant_id), error=str(exc))
        return  # No retry. No row state to clean up.

    # Txn 3: verify + upsert
    async with sm() as session:
        latest_now = (await session.execute(
            select(Resume)
            .where(
                Resume.applicant_id == applicant_id,
                Resume.parse_status == ResumeParseStatus.PARSED,
                Resume.deleted_at.is_(None),
            )
            .order_by(Resume.created_at.desc())
            .limit(1)
        )).scalar_one_or_none()
        if latest_now is None or latest_now.parsed_json is None:
            _log.info("embed.stale-no-parsed-resume", applicant_id=str(applicant_id))
            return
        parsed_now = ParsedResume.model_validate(latest_now.parsed_json)
        applicant_now = await session.get(Applicant, applicant_id)
        if applicant_now is None:
            return
        _, content_hash_now = canonicalize_profile(parsed_now, full_name=applicant_now.full_name)
        if content_hash_now != content_hash:
            _log.info(
                "embed.stale-content-aborted",
                applicant_id=str(applicant_id),
                computed_hash=content_hash,
                current_hash=content_hash_now,
            )
            return

        stmt = pg_insert(ApplicantEmbedding).values(
            applicant_id=applicant_id,
            embedding=result.values,
            model_name=result.model_name,
            canonicalized_text_hash=content_hash,
            input_tokens=result.input_tokens,
        ).on_conflict_do_update(
            index_elements=[ApplicantEmbedding.applicant_id],
            set_={
                "embedding": result.values,
                "model_name": result.model_name,
                "canonicalized_text_hash": content_hash,
                "input_tokens": result.input_tokens,
                "updated_at": func.now(),
            },
        )
        await session.execute(stmt)
        await session.commit()

    _log.info(
        "embed.complete",
        applicant_id=str(applicant_id),
        model_name=result.model_name,
        input_tokens=result.input_tokens,
    )
```

- [ ] **Step 3:** Hold the commit until Task 7 wires the dispatch.

---

### Task 7: Dispatch from `parse_resume` Txn3

**Files:** `workers/tasks/parse.py`.

- [ ] **Step 1:** In `_parse_resume_async`, after the final commit inside Txn3 (i.e., after the `_log.info("parse.complete", ...)` line) add:

```python
    # Dispatch async embedding — broker outages MUST NOT fail the parse because
    # parsed_json is already durable. Admin tooling can replay missing
    # applicant_embeddings rows after the broker recovers.
    try:
        from kpa.workers.tasks.embed import embed_applicant
        embed_applicant.delay(str(resume.applicant_id))
    except Exception as exc:
        _log.warning(
            "embed.dispatch-failed",
            applicant_id=str(resume.applicant_id),
            resume_id=str(resume_id),
            error_type=type(exc).__name__,
            error_message=str(exc),
            exc_info=True,
        )
```

`resume.applicant_id` is in scope from the Txn3 session — verify it's accessible there; if the variable name differs, adjust.

- [ ] **Step 2:** Commit Tasks 6 + 7 together.
```bash
git add api/src/kpa/workers/tasks/embed.py api/src/kpa/workers/celery_app.py api/src/kpa/workers/tasks/parse.py
git commit -m "feat(api): embed_applicant Celery task + dispatch from parse Txn3"
```

---

### Task 8: Integration tests

**Files:** `tests/integration/test_embed_worker.py` (create), `tests/integration/test_parse_pipeline.py` (modify), `tests/integration/conftest.py` (override the embedding provider).

- [ ] **Step 1:** In `tests/integration/conftest.py`, add a `embedding_provider` fixture:

```python
@dataclass
class FakeEmbeddingProvider:
    """Deterministic 1536-dim vector derived from sha256 of the input text."""
    calls: list[tuple[str, EmbeddingTask, str | None]] = field(default_factory=list)

    async def encode(self, *, text, task, title=None):
        self.calls.append((text, task, title))
        h = hashlib.sha256(text.encode()).digest()
        # Tile the 32 bytes into 1536 floats in [-1, 1].
        values = [((b / 255.0) * 2.0 - 1.0) for b in (h * 48)][:1536]
        return EmbeddingResult(values=values, model_name="fake-test-model", input_tokens=len(text) // 4)

@pytest.fixture
def embedding_provider() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()
```

Wire it in via `app.dependency_overrides[get_embedding_provider]` in `async_client` and `client` fixtures, parallel to `get_google_verifier`.

- [ ] **Step 2:** `test_embed_worker.py`:

```python
@pytest.mark.integration
async def test_embed_after_parse_writes_row(
    pipeline_client, migrated_db, embedding_provider, ...
) -> None:
    """Full flow: upload + parse + embed all run eager; row exists with right shape."""
    # Reuses _make_applicant_direct + _tiny_pdf_with from test_parse_pipeline.py
    # After the upload response, query applicant_embeddings; assert one row
    # with len(embedding)==1536, model_name=="fake-test-model",
    # canonicalized_text_hash is sha256 hex.

@pytest.mark.integration
async def test_rerun_with_same_content_is_noop(
    async_client, session, embedding_provider, ...
) -> None:
    """Call embed_applicant twice; second call must not invoke the provider."""
    # Trigger once via the upload route; clear embedding_provider.calls;
    # call embed_applicant.delay(applicant_id) again directly; assert calls is empty.

@pytest.mark.integration
async def test_stale_content_aborts_in_txn3(
    async_client, session, embedding_provider, monkeypatch
) -> None:
    """Race: between Txn1 and Txn3, change parsed_json; assert no upsert."""
    # Monkeypatch _embed_applicant_async to inject a session.execute that
    # mutates the resume's parsed_json between transactions. Easiest: patch
    # provider.encode to mutate parsed_json before returning.

@pytest.mark.integration
async def test_dispatch_resilient_to_embed_broker_failure(
    async_client, session, monkeypatch
) -> None:
    """If embed_applicant.delay() raises, parse_resume still commits PARSED."""
    # Monkeypatch embed_applicant.delay to raise ConnectionError;
    # upload + parse; assert resume.parse_status == PARSED and no
    # applicant_embeddings row exists.
```

- [ ] **Step 3:** Modify `test_parse_pipeline.py::test_upload_then_parse_populates_parsed_json` to add:
```python
emb = (await session.execute(
    select(ApplicantEmbedding).where(ApplicantEmbedding.applicant_id == applicant_id)
)).scalar_one()
assert len(emb.embedding) == 1536
```

- [ ] **Step 4:** Run them:
```bash
uv run pytest -v tests/integration/test_embed_worker.py tests/integration/test_parse_pipeline.py
```

- [ ] **Step 5:** Commit.
```bash
git add api/tests/integration/test_embed_worker.py api/tests/integration/test_parse_pipeline.py api/tests/integration/conftest.py
git commit -m "test(api): full upload → parse → embed pipeline + idempotency + race"
```

---

### Task 9: Documentation deltas

**Files:** `IMPLEMENTATION_SPEC.md`, `CLAUDE.md`, `api/README.md`.

- [ ] **Step 1:** Spec deltas:
  - §5: `vector(1024)` → `vector(1536)` in the `applicant_embeddings` table sketch. Add a one-line note: "Dim chosen per design doc 2026-05-19-embedding-worker."
  - §6.1 step 5: replace "Computes an embedding ... inserts into applicant_embeddings" with "Dispatches `embed_applicant.delay(applicant_id)` from Txn3. The worker computes the embedding asynchronously and upserts into `applicant_embeddings`."
  - §7: append a paragraph: "Note: `gemini-embedding-2` does not accept the `task_type` param — task is encoded via prompt prefix at the provider impl layer. The `EmbeddingProvider.encode()` interface accepts an `EmbeddingTask` enum + optional `title` to keep call sites provider-agnostic."

- [ ] **Step 2:** `CLAUDE.md` — add a new subsection under `## Architecture — non-obvious bits`, after the "Parse worker" section:

```markdown
### Embedding worker (Gemini)

- **One vector per applicant** (`applicant_embeddings.applicant_id UNIQUE`). Multi-resume applicants embed the latest parsed resume.
- **Idempotency via `canonicalized_text_hash`** on the row. The worker computes the canonical profile text + sha256 in Txn1, bails if hash matches the existing row. No provider call, no row write.
- **3-transaction split** mirrors `parse_resume`: Txn1 gate; Txn2 (no DB) Gemini call; Txn3 re-verify hash hasn't drifted, UPSERT via `ON CONFLICT (applicant_id) DO UPDATE`. Don't collapse.
- **Dispatched from `parse_resume` Txn3** post-commit, fire-and-forget. Same broad `except Exception` + `_log.warning("embed.dispatch-failed", exc_info=True)` as the upload-route → parse dispatch. Don't tighten.
- **Provider task via prompt prefix.** `gemini-embedding-2` does not accept `task_type`. `GeminiEmbeddingProvider.encode()` formats internally; call sites pass `EmbeddingTask.DOCUMENT` / `.QUERY` and an optional `title`.
- **Pgvector + HNSW + cosine.** New extension (`vector`); index uses `vector_cosine_ops` to match §6.3 hybrid scoring. Dim is config-driven via `KPA_EMBEDDING_DIM` (default 1536; must match `Vector(N)` in the migration).
- **No `embed_status` column.** The embedding either exists or it doesn't — no "embedding" intermediate state shown to users. If retry exhaustion leaves no row, the next parse completion re-dispatches.
- **Local worker becomes** `celery ... -Q parse,embed` (single worker, two queues) or run a second worker.
```

- [ ] **Step 3:** `api/README.md`:
  - Env-vars table: three new rows.
  - Worker command in the Redis section: update `-Q parse` to `-Q parse,embed`.

- [ ] **Step 4:** Commit.
```bash
git add IMPLEMENTATION_SPEC.md CLAUDE.md api/README.md
git commit -m "docs(api): spec/README/CLAUDE deltas for embedding worker"
```

---

### Task 10: Full suite + lint + types

- [ ] **Step 1:** From `api/`:
```bash
uv run pytest -v
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy
```
Expected: all green. If anything outside this slice's files breaks, stop and investigate — the only cross-file change should be the dispatch wiring in `parse.py`.

---

### Task 11: Open the PR

- [ ] **Step 1:**
```bash
git push -u origin feat/p1.3-embedding-worker
gh pr create --title "P1.3: embedding worker — Gemini embedding-2 @ 1536" --body "$(cat <<'EOF'
## Summary
- New `embed_applicant` Celery task: reads latest parsed resume, canonicalizes the profile, calls Gemini `embedding-2` (1536-dim), upserts into `applicant_embeddings`
- Dispatched fire-and-forget from `parse_resume` Txn3
- 3-transaction split with sha256 idempotency gate (`canonicalized_text_hash`)
- New `pgvector` dep + extension; HNSW + `vector_cosine_ops` index

Spec: `docs/superpowers/specs/2026-05-19-embedding-worker-design.md`

## Test plan
- [ ] `uv run pytest -v tests/unit/test_canonicalize.py tests/unit/test_gemini_provider.py` — clean
- [ ] `uv run pytest -v tests/integration/test_embed_worker.py` — 4 passed
- [ ] `uv run pytest -v tests/integration/test_parse_pipeline.py` — 2 passed (now also asserts on embedding row)
- [ ] `uv run pytest -v` full suite — all passed
- [ ] `uv run ruff check src/ tests/` + `uv run mypy` — both clean

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Paste the PR URL back.

---

## Out of scope (intentional)

Carried over from the spec:

- `job_embeddings` + `embed_job` task — lands with P2.
- `PATCH /v1/me/applicant`-driven re-embed — needs the endpoint first.
- Nightly stale re-embed beat task — needs prompt versioning.
- Vertex AI deployment path — P4 DPDP.
- Embedding quality eval / F1 gate — separate slice.
- Provider-level `sha256(text)` LRU — the row-level hash provides equivalent dedup for the only current call site.

---

## Self-review notes (for the executor)

Four things to double-check before pushing:

1. **`google-genai` exception class names match the installed version.** Run `uv run python -c "from google.genai import errors; print([n for n in dir(errors) if not n.startswith('_')])"` and align `gemini.py`'s except clauses. If the SDK renamed `ClientError` → `BadRequestError`, adjust.
2. **`Resume.parsed_json` shape matches `ParsedResume`.** If the library parser writes a subset, the `ParsedResume.model_validate(...)` call in Txn1 will raise — adjust `canonicalize_profile` to tolerate missing optional fields rather than hardcoding all of them.
3. **`pgvector` extension privileges.** If `CREATE EXTENSION vector` fails for the `kpa` role on either DB, the migration step in the integration conftest dies before any test runs. Document a one-shot `psql -d postgres -c "ALTER ROLE kpa SUPERUSER;"` (dev only) or pre-create the extension as `postgres`.
4. **Eager-mode thread-hop is wired correctly.** When `KPA_CELERY_TASK_ALWAYS_EAGER=true`, the `embed_applicant.delay(...)` call inside `parse_resume`'s Txn3 will execute on a running event loop. The thread-hop in `embed.py` must mirror the one in `parse.py:72-83` exactly — copy-paste the helper, don't try to share.
