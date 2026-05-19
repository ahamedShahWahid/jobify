# Embedding worker — design

**Date:** 2026-05-19
**Spec ref:** `IMPLEMENTATION_SPEC.md` §5 (data model — `applicant_embeddings`), §6.1 step 5 (parse + embed pipeline), §7 (`EmbeddingProvider` interface), §13 P1 ("embedding worker + status push remain").
**Status:** Draft — pending approval.

Next P1 slice. The parse worker (PR #6) leaves rows at `parse_status=parsed` with structured `parsed_json` but produces no vector. This worker reads parsed rows, computes an embedding via Gemini, and writes `applicant_embeddings`. P2 matching (§6.3) is unblocked once this lands and `job_embeddings` follows in P2.

## Why this slice

Three things gate on this:

1. **P2 matching cannot start.** Hybrid scoring in §6.3 cosines `applicant_embedding` against `job_embedding`. Until applicants have vectors, recruiter-facing matches are paper-only.
2. **The BRD's "first match in 10 min" budget** (§6.1 target) allots 1 s of that to embedding. Establishing the worker now gives us measurable p50 latency well before P2 needs to hit the budget end-to-end.
3. **The provider/dim decision was just resolved** (see "Decisions resolved" below) — keeping it un-coded leaves the schema's `vector(N)` placeholder stale and risks drift if the decision is revisited in a different context.

## Decisions resolved during brainstorming

| # | Decision | Resolution |
|---|---|---|
| 1 | Embedding provider | **Gemini Developer API direct** (`generativelanguage.googleapis.com`). Vertex AI in `asia-south1` is the swap-target for DPDP, deferred to P4. |
| 2 | Model | `gemini-embedding-2` — multimodal, multilingual (100+ languages), Matryoshka-truncatable. |
| 3 | Output dimension | **1536** — Google's "medium recommended" dim; ~99% quality of full 3072 at half the storage. Spec §5 placeholder `vector(1024)` becomes `vector(1536)` (doc-only change — no table exists yet). |
| 4 | Task encoding | `gemini-embedding-2` does **not** accept the `task_type` parameter. Task is encoded via prompt prefix: `title: {full_name} \| text: {canonicalized_profile}` for the applicant (document) side; `task: search result \| query: {job_query}` for the job (query) side in P2. |
| 5 | Dispatch trigger | **From the parse worker's Txn3**, fire-and-forget after `parse_status=parsed` is committed. Same broad-except + `_log.warning("dispatch.failed", ...)` pattern as the upload route's `parse_resume.delay()`. |
| 6 | Idempotency gate | **`canonicalized_text_hash`** column on `applicant_embeddings`. If the hash of the canonicalized profile matches the existing row, the worker no-ops. Avoids re-spending Gemini tokens on identical content. |
| 7 | Per-applicant cardinality | **One current embedding per applicant** — `applicant_id` is `UNIQUE`. Multi-resume applicants get embeddings from the *latest parsed* resume. Older resumes' content is unreachable from the matching path. |
| 8 | Celery queue | New `embed` queue per spec §8. Local dev runs `-Q parse,embed` or a second worker. |

## Surface

This is a Celery task, not an HTTP endpoint. Two new things ship:

**1. Task entry point** in `api/src/kpa/workers/tasks/embed.py`:

```python
@celery_app.task(
    name="kpa.embed_applicant",
    bind=True,
    max_retries=3,
    autoretry_for=(TransientEmbeddingError,),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    acks_late=True,
)
def embed_applicant(self, applicant_id_str: str) -> None: ...
```

Same shape as `parse_resume`: sync entry that wraps an asyncio body, eager-mode thread-hop, mark-failed-before-final-raise discipline.

**2. New model** `ApplicantEmbedding` in `db/models.py`:

```python
class ApplicantEmbedding(Base):
    __tablename__ = "applicant_embeddings"

    id: Mapped[UuidPK]
    applicant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kpa.applicants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,                              # one current vector per applicant
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    canonicalized_text_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    deleted_at: Mapped[DeletedAt]
```

`model_name` is on the row (not implicit) so a future Vertex swap, dim change, or prompt-version bump can identify which rows need re-embedding without consulting a global config. `input_tokens` is for cost-tracking dashboards in P3+.

### Provider interface

`api/src/kpa/integrations/embeddings/base.py`:

```python
class EmbeddingTask(StrEnum):
    # Applicant/job profile content (document side of asymmetric retrieval).
    DOCUMENT = "document"
    # Recruiter or applicant-initiated query (query side). Lands in P2.
    QUERY = "query"

@dataclass(frozen=True)
class EmbeddingResult:
    values: list[float]
    model_name: str
    input_tokens: int

class EmbeddingProvider(Protocol):
    async def encode(
        self,
        *,
        text: str,
        task: EmbeddingTask,
        title: str | None = None,
    ) -> EmbeddingResult: ...
```

`GeminiEmbeddingProvider` impl:
- `DOCUMENT` task formats as `title: {title or 'none'} | text: {text}`.
- `QUERY` task formats as `task: search result | query: {text}`.
- Reads `KPA_GEMINI_API_KEY` from settings.
- Reads `KPA_EMBEDDING_MODEL` (default `"gemini-embedding-2"`) and `KPA_EMBEDDING_DIM` (default `1536`) so the model and Matryoshka truncation are config-driven, not hardcoded at call sites.
- Maps Gemini SDK exceptions: 429 / 5xx → `TransientEmbeddingError`; 400 / malformed input → `EmbeddingProviderError`.

The interface is deliberately narrower than spec §7's sketch (`encode(text) -> vec`) — it carries the model name and token count out of the provider so the worker can persist them without a second call.

### Canonicalize-profile helper

`api/src/kpa/integrations/embeddings/canonicalize.py` exposes:

```python
def canonicalize_profile(parsed: ParsedResume, *, full_name: str) -> tuple[str, str]:
    """Return (canonicalized_text, sha256_hex_hash)."""
```

Deterministic output — same `ParsedResume` always produces the same text and hash. Shape (one section per line, stable ordering, sorted skills):

```
{full_name}
Skills: {sorted_unique_lowercased_skills, comma-joined}
Experience: {sum_years_total}y total
- {role.title} @ {role.company} ({role.start}–{role.end or 'present'}): {role.description}
- ...
Education:
- {edu.degree}, {edu.institution} ({edu.start}–{edu.end})
- ...
Certifications: {sorted_certifications, comma-joined}
```

The hash is sha256 of this text. Storing it on the row is what makes re-runs cheap: same content → no API call, no row write.

## Implementation — 3-transaction split

Mirrored from `parse_resume`. Same rationale: holding a row lock across a network call to Gemini would starve other writers.

**Txn 1 — gate.**
```python
async with sm() as session:
    applicant = await session.get(Applicant, applicant_id)
    if applicant is None or applicant.deleted_at is not None:
        return  # log + skip
    latest_resume = (await session.execute(
        select(Resume).where(
            Resume.applicant_id == applicant_id,
            Resume.parse_status == ResumeParseStatus.PARSED,
            Resume.deleted_at.is_(None),
        ).order_by(Resume.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if latest_resume is None or latest_resume.parsed_json is None:
        return  # nothing to embed yet
    parsed = ParsedResume.model_validate(latest_resume.parsed_json)
    text, content_hash = canonicalize_profile(parsed, full_name=applicant.full_name)
    existing = (await session.execute(
        select(ApplicantEmbedding).where(ApplicantEmbedding.applicant_id == applicant_id)
    )).scalar_one_or_none()
    if existing is not None and existing.canonicalized_text_hash == content_hash:
        return  # idempotent skip
```

**Txn 2 — no DB.** Outside any DB session:
```python
result = await provider.encode(
    text=text, task=EmbeddingTask.DOCUMENT, title=applicant.full_name,
)
```
`TransientEmbeddingError` here propagates and Celery autoretries. `EmbeddingProviderError` is logged + the worker exits cleanly (no row mutation needed; no `failed` state exists for this table by design — the next parse completion will re-dispatch).

**Txn 3 — upsert.**
```python
async with sm() as session:
    # Re-load + verify content hash hasn't drifted (e.g. a newer resume parsed
    # mid-flight). If it has, abandon — the newer dispatch will produce the
    # right vector.
    latest_resume_now = await _load_latest_parsed_resume(session, applicant_id)
    if latest_resume_now is None or latest_resume_now.parsed_json is None:
        return
    _, content_hash_now = canonicalize_profile(...)
    if content_hash_now != content_hash:
        _log.info("embed.stale-content-aborted", applicant_id=...)
        return
    # Upsert via Postgres ON CONFLICT (applicant_id) DO UPDATE.
    stmt = insert(ApplicantEmbedding).values(
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
```

### Dispatch from `parse_resume`

In `parse.py:_parse_resume_async` Txn 3, after `resume.parse_status = ResumeParseStatus.PARSED` commits:

```python
try:
    from kpa.workers.tasks.embed import embed_applicant
    embed_applicant.delay(str(resume.applicant_id))
except Exception as exc:
    _log.warning(
        "embed.dispatch-failed",
        applicant_id=str(resume.applicant_id),
        resume_id=str(resume_id),
        error_type=type(exc).__name__,
        exc_info=True,
    )
```

Same broad-except + log discipline as the upload route's parse dispatch. The parse result is durable; admin tooling will replay missing embeddings.

## Schema delta + migration

Single new revision `0004_applicant_embeddings.py`:

```python
def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "applicant_embeddings",
        sa.Column("id", ..., primary_key=True),
        sa.Column("applicant_id", sa.UUID, sa.ForeignKey("kpa.applicants.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("model_name", sa.String(64), nullable=False),
        sa.Column("canonicalized_text_hash", sa.CHAR(64), nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False),
        sa.Column("created_at", ..., server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", ..., server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", ..., nullable=True),
        schema="kpa",
    )
    op.execute(
        "CREATE INDEX ix_applicant_embeddings_hnsw ON kpa.applicant_embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    )
```

`pgvector` extension is new; `CREATE EXTENSION vector` must run before the table create. HNSW index uses cosine ops because §6.3 specifies cosine similarity.

## Tests

Unit:
- `test_canonicalize.py` — same `ParsedResume` produces identical text + hash; field-ordering invariance; skills sorted-unique-lowercased.
- `test_gemini_provider.py` — mock the embed endpoint; verify DOCUMENT task formats as `title: ... | text: ...`; verify QUERY task formats as `task: search result | query: ...`; verify 429 → `TransientEmbeddingError`; verify 400 → `EmbeddingProviderError`.

Integration (require local Postgres + `pgvector` extension installed):
- `test_embed_worker.py::test_embed_after_parse_writes_row` — parse_resume runs eager, embed_applicant fires, applicant_embeddings has a 1536-dim vector with the right hash + model_name.
- `test_embed_worker.py::test_rerun_with_same_content_is_noop` — call twice; second call must skip the provider entirely (assert provider mock called once).
- `test_embed_worker.py::test_stale_content_aborts_in_txn3` — race scenario: between Txn1 and Txn3, replace `parsed_json` so the hash differs; assert the worker logs `embed.stale-content-aborted` and writes nothing.
- `test_embed_worker.py::test_dispatch_resilient` — embed_applicant.delay() raises in eager mode; parse_resume still commits PARSED; applicant_embeddings has no row.

The parse-pipeline integration tests in `test_parse_pipeline.py` get one new assertion: after the eager parse, an `applicant_embeddings` row exists.

## Config + env

Three new settings (`api/src/kpa/settings.py`):

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `KPA_GEMINI_API_KEY` | yes (prod) | — | Gemini Developer API key |
| `KPA_EMBEDDING_MODEL` | no | `gemini-embedding-2` | Model identifier |
| `KPA_EMBEDDING_DIM` | no | `1536` | Matryoshka output dimension (must match `Vector(N)` in the table) |

Tests inject a fake provider via `app.dependency_overrides` — no real API key needed for the suite. `concurrent_async_client`-style fixtures stay unchanged.

`celery_app.py` registers `embed` in the queue list. Local worker becomes:
```
uv run --env-file=.env celery -A kpa.workers.celery_app worker \
    --pool=solo --concurrency=1 -Q parse,embed --loglevel=info
```

## Out of scope (intentional)

- **`job_embeddings` table + `embed_job` task.** Lands with P2 recruiter posting. Will use the same provider interface and `Vector(1536)`.
- **`PATCH /v1/me/applicant`-driven re-embed.** The profile-edit endpoint doesn't exist yet; when it does, it dispatches `embed_applicant.delay(applicant_id)` itself.
- **Nightly stale re-embed beat task.** Needed when prompt versioning or model version bumps. Not until P3+.
- **Vertex AI deployment path.** DPDP-residency swap deferred to P4. The provider interface makes this a config + impl change, not a schema change (1536 dim is supported on Vertex too).
- **Embedding quality eval / F1 gate.** Spec §13 P1 sets parse F1 ≥ 0.85 before P2; embedding quality has no equivalent gate yet — relevance is measured downstream in §6.3 hybrid scoring.
- **Caching at the provider level on `sha256(text)`.** Spec §7 mentions this; our `canonicalized_text_hash` on the row already provides the same guarantee for the only call site we have. A provider-level LRU is justified only when we start re-encoding the same text from multiple call sites.

## Spec deltas

Three small edits to `IMPLEMENTATION_SPEC.md`:

1. **§5** — change `applicant_embeddings.embedding` from `vector(1024)` to `vector(1536)`; cite this design doc for the rationale.
2. **§6.1 step 5** — clarify that "computes an embedding" is dispatched async from `parse_resume`'s Txn3 via `embed_applicant.delay()`, not done inline.
3. **§7** — note that `gemini-embedding-2` encodes task via prompt prefix; the `EmbeddingProvider` interface gains an `EmbeddingTask` enum + optional `title` param.

## Branch + PR

- Branch: `feat/p1.3-embedding-worker`
- Base: `main` (no preceding PR dependency)
- Estimated: 4 commits — (a) provider interface + Gemini impl + canonicalize helper, (b) model + migration, (c) worker task + dispatch wiring, (d) tests + spec deltas.
- PR target: `main`
