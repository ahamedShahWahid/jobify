# CLAUDE.md — core (`jobify` domain package)

Load-bearing invariants for the FastAPI- and Celery-free domain package (`core/src/jobify`): db models + Alembic migrations, shared settings contracts, integrations (storage, parser, embeddings, email, scoring, explainer), consent/DSR/audit, eval, and durable outbox primitives. Celery configuration and task implementations live in `worker/`. Auto-loaded when working under `core/`. Repo overview + universal conventions are in the root `CLAUDE.md`.

> Each section names its paired design doc in `docs/superpowers/specs/` (the **why** + full reserved-slug tables). Below = rules that cause a bug if violated and aren't obvious from the code. Task-side invariants for the parse/embed/score Celery tasks live in `worker/CLAUDE.md`.

## Soft delete model

Every domain table: `id` (uuid4), `created_at`, `updated_at`, `deleted_at TIMESTAMPTZ NULL`. Live queries filter `deleted_at IS NULL`; uniqueness via partial indexes `WHERE deleted_at IS NULL` (e.g. `User.ix_users_email_live`). New tables reuse the `CreatedAt`/`UpdatedAt`/`DeletedAt` `Annotated` types in `db/models.py`. `Base.__table_args__` is typed `Any` + `# noqa: RUF012` — don't "fix" the noqa.

## Applicant preferences (`applicant_preferences`) — spec `2026-07-01-resume-review-preferences-design.md`

- **One live row per applicant** (partial-unique `ix_applicant_preferences_applicant_live`), **eagerly created at signup** by `AuthService._upsert_identity` (like consent seeding) — the API assumes presence (missing live row → 500). Workers still outer-join defensively for seeded/test applicants, with `deleted_at IS NULL` in the JOIN's **ON clause** so a soft-deleted row degrades to "no prefs" rather than dropping the applicant (see `worker/CLAUDE.md` → Scoring).
- **`desired_role` is varchar in DB, `RoleCategory` StrEnum at the boundary** (same precedent as consent scopes — adding a value is a plain Python enum edit, no PG-enum migration). It is **capture-only**: scoring reads `locations`/`expected_ctc`/`years_experience`, never `desired_role` — its absence from the rescore triggers is deliberate.
- `expected_ctc >= 0` enforced by DB CHECK (`ck_applicant_preferences_expected_ctc_nonneg`); upper bound + locations cardinality (≤10, each ≤100 chars) enforced at the API boundary only.

## Audit logs (`audit_log()`) — spec `2026-05-28-audit-logs-substrate-design.md`

- **Append-only, caller-owns-txn:** flushes one row in the caller's txn (no commit, no fire-and-forget; rolls back with the business action). The **documented exception** to soft-delete: `AuditLog` skips the `Created/Updated/DeletedAt` types and never filters `deleted_at IS NULL`. No UPDATE/DELETE.
- `actor_user_id` is `ON DELETE SET NULL` (so a DSR hard-delete leaves the audit row, re-identification impossible). `actor_role` is a plain-TEXT **snapshot** (`'system'` valid for cron/worker, `actor=None`). `audit_log(actor=None, actor_role=None)` raises `ValueError`.
- Slugs dotted-lowercase-verb-past; reserved prefixes `resume.*` `application.*` `job.*` `consent.*` `user.*` `admin.*` `auth.*` `employer.*` (table in spec §4).
- **structlog FIRST, `audit_log()` SECOND, then side-effect** (canonical `jobify_api.routes.applications:recruiter_download_application_resume`). structlog → Fluent Bit → Elasticsearch is the live channel; the DB row is durable — complementary.

## Consent + channel prefs — spec `2026-05-29-consent-channel-prefs-design.md`

- **`user_consents` = state; `audit_logs` = history.** `set_consent(...)` is the ONLY path writing a `consent.*` audit row (same txn); no-op flips write none. Don't hand-write consent audit rows.
- **`ON DELETE CASCADE` on `user_id`** (opposite of audit_logs) — consent vanishes with the user; history survives via `actor_user_id SET NULL`.
- **Eager seeding at signup** — `_upsert_identity` calls `seed_default_consents(...)`; later reads are plain SELECTs. Default changes affect only NEW signups. `email_transactional` defaults `true` — signup UI MUST notify the user.
- **Sweep gate:** `sweep_notifications._dispatch_one` checks consent between user-load and dispatch. No consent → `status=CANCELLED`, terminal (re-grant doesn't resurrect). `get_consent` raising `LookupError` (seeding skipped — pre-P4-B / DSR-cascaded) → falls back to `DEFAULT_CONSENTS[scope]`; backfill `jobify-seed-consents`. Inbox excludes `CANCELLED` + `FAILED`.
- Scopes are `StrEnum` at the boundary, TEXT in DB; reserved scopes ship default `false` so impls skip an enum migration.
- **Adding a Postgres enum value** can't share a txn with other DDL. Try `op.get_context().autocommit_block()` first; our async setup trips on `_in_external_transaction` — Alembic 0014's `bind.commit()` + `run_async(...)` is a **documented exception, DO NOT copy unprompted** (document the error first).

## Match explanations — specs `p2.4` + `2026-05-28-llm-match-explanations-design.md`

The explainer modules live here (`jobify` integrations); they are invoked inline by the score workers (see `worker/CLAUDE.md`).

- **`matches.explanation` JSONB** `{fit, caveat, generator, generator_version}`, nullable. Generated inline in both score workers.
- **`MatchExplainer` Protocol** routes two impls; workers call `await get_match_explainer().explain(ctx)`, call site unchanged. **`explain()` NEVER raises** — scoring is never failed by the explainer.
- **`TemplatedExplainer`** (`explainer.py`, wraps pure `templated_explanation()`) deterministic. **`GeminiMatchExplainer`** (`llm_explainer.py`) surfaced-only (if `ctx.total < ctx.threshold` returns templated, no Gemini); any failure logs `explain.llm-failed` (with `raw_text`) + falls back to templated.
- **`thinking_budget=0` is load-bearing** in the explainer's `GenerateContentConfig` — gemini-2.5 thinks by default and thought tokens count against `max_output_tokens`; with the 200 cap, thinking starved the output and EVERY explain silently fell back to templated (the never-raise contract hides it). Watch `generator` in stored explanations, not just error logs.
- **Selection:** `JOBIFY_MATCH_EXPLAINER` = `"llm"` (default, Gemini) | `"templated"` (dev fallback, no `JOBIFY_GEMINI_API_KEY`). Model `JOBIFY_MATCH_EXPLAINER_MODEL` (`gemini-2.5-flash`). Factory `get_match_explainer()` lazy-singleton. **`explainer.py` does NOT import `google.genai`** (separate module; factory does `from google import genai` lazily). `patched_match_explainer` mirrors the embedding fixture (three modules + cache).
- **`GENERATOR_VERSION` bumps on semantic template/prompt change** — flag template/prompt edits.

## Parse F1 quality gate

- **Gold dataset `core/data/parse_eval/`** (`<id>.txt` + `<id>.expected.json`); raw text (PDF/DOCX extraction bypassed — gate measures parser heuristics).
- **`uv run pytest -m eval`** → `test_library_parser_meets_quality_gate` → `jobify.eval.parse_f1.eval_gold_dataset()`. CI runs it (`lint-types-unit-eval`, no DB) before integration.
- **Gate** (spec §13 P1): macro-F1 ≥ 0.85; floors `email ≥ 0.95`/`phone ≥ 0.85`/`name ≥ 0.70`/`skills ≥ 0.75`. **Only those 4 fields gate** (others print only). Set-skills F1 counts FPs (measures `_extract_skills` over-match drift).
- New gold example: drop a pair with the next id, re-run `-m eval -v -s`; if it tanks a floor, fix the expectation or document the limitation.

## Seeding — spec `2026-05-20-p2.0-jobs-and-seeding-design.md`

CLI entrypoint `jobify-seed-jobs` AND its loader logic live in `api/src/jobify_api/scripts/seed_jobs.py`; only the 44-line data fixture (`core/data/sample_jobs.json`) lives here.

- **`employers`/`jobs` via CLI** (`uv run jobify-seed-jobs` reads `core/data/sample_jobs.json`, upserts), not migrations. Idempotency: `employers.name_norm` (DB partial-UNIQUE) + `(jobs.employer_id, lower(jobs.title))` (script-only). JSON uses `posted_days_ago: int` (→ `now() - timedelta`) so it doesn't age.
- **Updates preserve human state:** `employers.name` never overwritten; `verified_at` set only when `NULL`.
- **`_apply_in_session(session, payload, report)` is the test seam** (CLI's `_apply()` opens its own engine; tests pass the savepoint session). It stages one durable `jobify.embed_job` outbox event per inserted/updated job in the same transaction.
- **Drift guard** `test_loader_against_sample_jobs_json` asserts `employers==10, jobs==27` — update in the same commit.
