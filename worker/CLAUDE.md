# CLAUDE.md — worker (`jobify_worker` Celery daemon)

Load-bearing invariants for the Celery tasks (`worker/src/jobify_worker`): parse, embed, score, notifications-sweep, plus runtime singletons. Auto-loaded when working under `worker/`. Repo overview + universal conventions are in the root `CLAUDE.md`; the domain modules these tasks call (parser, embeddings, explainer, scoring) live in `core/` — see `core/CLAUDE.md`.

> Each section names its paired design doc in `docs/superpowers/specs/` (the **why** + full reserved-slug tables). Below = rules that cause a bug if violated and aren't obvious from the code.

## Worker runtime (shared by all tasks)

- **Workers import `settings` from `celery_app`, never construct `Settings()`** — a second module-level instance is invisible to test `monkeypatch.setenv`. The worker engine's `NullPool` is load-bearing (fresh `asyncio.run()` loop per task; pooled asyncpg connections bind to dead loops).
- **Tasks are dispatched by name** via `jobify.celery_app.enqueue("jobify.<task>", …)`; routing is configured in `core/src/jobify/celery_app.py`. Cross-task dispatch (e.g. parse → embed → score) is post-commit and fire-and-forget under a broad `except Exception` — **don't tighten** (a broker outage must not fail the durable upstream write).
- **Eager mode** (`JOBIFY_CELERY_TASK_ALWAYS_EAGER=true`) runs tasks inline for tests; see Parse worker for the running-loop caveat.

## Parse worker — spec `2026-05-18-resume-parse-worker-design.md`

- **Fire-and-forget after commit:** `parse_resume.delay()` wrapped in broad `except Exception` + `exc_info=True` (`dispatch.failed`). Broker outage MUST NOT fail an upload (row + blob durable). **Don't tighten the except.**
- **3-txn split** (`parse.py:_parse_resume_async`): Txn1 load + idempotency gate + mark `parsing`; (no DB) read blob + extract + parse; Txn3 reload, verify still `parsing`, write `parsed_json` + `parsed`. A lock across extraction starves writers — keep the split.
- **Retry:** `ParserError` → immediate `failed`; `TransientParserError` → autoretry ×3 exp backoff; unknown → wrapped. On exhaustion the row is marked `failed` BEFORE the raise (no wedge at `parsing`).
- **Eager mode + running loop:** with `JOBIFY_CELERY_TASK_ALWAYS_EAGER=true` inside an async request, `asyncio.run()` would explode — `parse.py` dispatches to a fresh thread. Tests rely on this.

## Embedding worker (Gemini) — spec `2026-05-19-embedding-worker-design.md`

- **One vector per applicant** (`applicant_embeddings.applicant_id UNIQUE`) — the *latest* parsed resume's canonical profile; older resumes unreachable from matching.
- **Idempotency via `canonicalized_text_hash`** — Txn1 computes text + sha256, bails on match (no provider call). **3-txn split** like parse: Txn1 gate; Txn2 (no DB) Gemini; Txn3 re-verify hash, UPSERT via `pg_insert(...).on_conflict_do_update(...)`. Dispatched from `parse_resume` Txn3, fire-and-forget (don't tighten).
- **Provider task via prompt prefix:** `gemini-embedding-2` does NOT accept `task_type` (that was `-001`). `encode()` formats internally; call sites pass `EmbeddingTask.DOCUMENT`/`.QUERY` + optional `title`.
- **Lazy provider resolution:** `embed.py` resolves via `get_embedding_provider()` (lazy-singleton in `celery_app.py`), never importing `GeminiEmbeddingProvider`. The `jobify.integrations.embeddings` `__init__` omits the provider from re-exports so `google.genai` isn't pulled in by test imports; impl users import from `...embeddings.gemini`.
- **`from module import name` test-patch gotcha:** modules holding a local `get_embedding_provider` reference aren't intercepted by patching `celery_app.get_embedding_provider` alone. `patched_embedding_provider` patches **three** modules (`celery_app`, `embed_job`, `embed`) + seeds the `_embedding_provider` cache. Mirror for any function imported-by-name across modules.
- **Pgvector + HNSW + cosine** (Migration 0004, `vector_cosine_ops`). Dim from `JOBIFY_EMBEDDING_DIM` (1536) — must match `Vector(N)` in the migration (mismatch errors on first insert). No `embed_status` column: it exists or doesn't; next parse re-dispatches.

## Scoring worker — spec `2026-05-20-p2.2-matches-and-scoring-design.md`

- **`matches` = applicant × job embedding join.** One row per `(applicant_id, job_id)` live pair, UPSERT on rescore via partial-UNIQUE `WHERE deleted_at IS NULL`.
- **Two workers, one `score` queue:** `score_applicant` (from `embed_applicant` Txn3) + `score_job` (from `embed_job` Txn3), post-commit, broad-except. Pure-Python cosine (`jobify.scoring.vector`). Explanations run via bounded `asyncio.gather` (`_EXPLAIN_CONCURRENCY=10`), not per-item awaits (the explainer itself lives in `core/` — see `core/CLAUDE.md` → Match explanations).
- **`surfaced_at` preserved on rescore** via `func.coalesce(Match.surfaced_at, case((literal(crosses_threshold), now()), else_=None))` — a later sub-threshold rescore does NOT unset it (feed monotonic).
- **`score_components` + `model_versions` JSONB** = eval substrate (replay weight/threshold A/B without rescoring). **Two-txn split** (no external call): Txn1 loads all (incl. `Employer.name`), Python computes, Txn2 UPSERTs in one commit. `TransientScoringError` wraps UPSERT failures for autoretry. Threshold `0.55` (`JOBIFY_MATCH_SURFACE_THRESHOLD`) + vector weight `0.6` (`JOBIFY_MATCH_VECTOR_WEIGHT`) env-driven; per-rule weights equal.

## Notifications outbox — spec `2026-05-20-p3.1-notifications-outbox-design.md`

Writers insert `notifications` rows from the api routes (apply, invite); the sweep task here dispatches them.

- **Outbox:** writers insert `notifications` on the event; `sweep_notifications` (beat) claims via `SELECT FOR UPDATE SKIP LOCKED`. Idempotency per `notifications.id`.
- **Email = `LoggingEmailChannel` stub** (logs `email.sent`, marks `sent`). Real SES: implement `EmailChannel` in `jobify/integrations/email/ses.py`, set `JOBIFY_EMAIL_CHANNEL=ses`.
- **Retry ×5**, backoff `min(60·2^(attempt-1), 3600) + jitter(0,30)` → `send_after`; exhaustion → `failed`.
- **Apply inserts TWO rows** (`email` + `in_app`); idempotent re-applies and re-apply-after-withdraw insert none. `GET /v1/notifications` excludes `failed` + `cancelled`.
- **Consent gate:** `_dispatch_one` checks consent between user-load and dispatch — see `core/CLAUDE.md` → Consent for the CANCELLED-terminal and `LookupError`-fallback rules.
