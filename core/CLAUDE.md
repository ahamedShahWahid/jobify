# CLAUDE.md — core (`jobify` domain package)

Load-bearing invariants for the FastAPI- and Celery-free domain package (`core/src/jobify`): db models + Alembic migrations, shared settings contracts, integrations (storage, parser, embeddings, email, scoring, explainer), consent/audit, eval, and durable outbox primitives (**DSR export/delete lives in `api/src/jobify_api/dsr/`**, not here — it needs the HTTP request context). Celery configuration and task implementations live in `worker/`. Auto-loaded when working under `core/`. Repo overview + universal conventions are in the root `CLAUDE.md`.

> Each section names its paired design doc in `docs/superpowers/specs/` (the **why** + full reserved-slug tables). Below = rules that cause a bug if violated and aren't obvious from the code. Task-side invariants for the parse/embed/score Celery tasks live in `worker/CLAUDE.md`.

## Soft delete model

Every domain table: `id` (uuid4), `created_at`, `updated_at`, `deleted_at TIMESTAMPTZ NULL`. Live queries filter `deleted_at IS NULL`; uniqueness via partial indexes `WHERE deleted_at IS NULL` (e.g. `User.ix_users_email_live`). New tables reuse the `CreatedAt`/`UpdatedAt`/`DeletedAt` `Annotated` types in `db/models.py`. `Base.__table_args__` is typed `Any` + `# noqa: RUF012` — don't "fix" the noqa.

## Applicant preferences (`applicant_preferences`) — spec `2026-07-01-resume-review-preferences-design.md`

- **One live row per applicant** (partial-unique `ix_applicant_preferences_applicant_live`), **eagerly created at signup** by `AuthService._upsert_identity` (like consent seeding), and backfilled for older applicants by migration 0028 — the API provisions a row that never existed but 500s on a soft-deleted-only row (see `api/CLAUDE.md`). Workers still outer-join defensively for seeded/test applicants, with `deleted_at IS NULL` in the JOIN's **ON clause** so a soft-deleted row degrades to "no prefs" rather than dropping the applicant (see `worker/CLAUDE.md` → Scoring).
- **`desired_role` is varchar in DB, `RoleCategory` StrEnum at the boundary** (same precedent as consent scopes — adding a value is a plain Python enum edit, no PG-enum migration). It is **capture-only**: scoring reads `locations`/`expected_ctc`/`years_experience`, never `desired_role` — its absence from the rescore triggers is deliberate.
- `expected_ctc >= 0` enforced by DB CHECK (`ck_applicant_preferences_expected_ctc_nonneg`); upper bound + locations cardinality (≤10, each ≤100 chars) enforced at the API boundary only.
- **language** ('en'|'hi', varchar+CHECK, AppLanguage StrEnum) IS a rescore trigger — the switch regenerates explanations in the new language via the normal rescore (scores identical). desired_role remains capture-only. Hindi templated + LLM explainer variants live in scoring/ (spec 2026-08-01-hindi-i18n-design.md); LLM failure for a Hindi ctx falls back to HINDI templated text, never English.

## Match feedback (`match_feedback`) — spec `2026-07-19-match-feedback-design.md`

- **Keyed on `(applicant_id, job_id)`, NOT match_id** — ratings must survive match-row rescore UPSERTs. One live row per pair (partial-unique `ix_match_feedback_applicant_job_live`); re-rate UPDATEs, clear soft-deletes, re-rate-after-clear inserts fresh (saved_jobs precedent).
- **`rating` is varchar+CHECK (`'up'/'down'`), `MatchFeedbackRating` StrEnum at the boundary** — same no-PG-enum precedent as consent scopes/desired_role.
- **PII: DSR-wired** — exported AND hard-deleted; pinned in `EXPECTED_PII_TABLES` (`tests/unit/dsr/test_dsr_coverage.py`).
- `rating='down'` excludes the job from that applicant's `/v1/feed` (see `api/CLAUDE.md`).

## Application stages (`applications.stage` + `application_stage_events`) — spec `2026-07-19-application-stages-design.md`

- **`status` = applicant lifecycle (applied/withdrawn); `stage` = recruiter pipeline** (varchar+CHECK `applied|shortlisted|interview|offer|hired|rejected`; `ApplicationStage` StrEnum at the boundary — the native-enum `status` is legacy, don't copy it). Withdrawal freezes stage; **re-apply resets stage to `applied` and writes a stage event with the applicant as actor**.
- **`application_stage_events` powers the applicant timeline** — append-only in practice, `actor_user_id` SET NULL (survives DSR), actor NEVER exposed to the applicant. DSR class: **export-only** (like `applications`) — exported, kept on delete; pinned in `_EXPORT_ONLY_TABLES`.
- **Every real transition, one txn:** structlog → `audit_log("application.stage_changed")` → event row → Notification (kind `application_stage_changed`, EMAIL + IN_APP). Same-stage PATCH = 200 no-op with none of those. Rejection copy is neutral ("moved forward with other candidates"); applicant-facing label is "Not selected".

## Audit logs (`audit_log()`) — spec `2026-05-28-audit-logs-substrate-design.md`

- **Append-only, caller-owns-txn:** flushes one row in the caller's txn (no commit, no fire-and-forget; rolls back with the business action). The **documented exception** to soft-delete: `AuditLog` skips the `Created/Updated/DeletedAt` types and never filters `deleted_at IS NULL`. No UPDATE/DELETE.
- `actor_user_id` is `ON DELETE SET NULL` — but note DSR only SOFT-deletes the user, so that action never actually fires; the audit row survives with its actor pointer intact and the user row's PII nulled. **PII inside `context` is a separate problem the FK cannot solve**: four employer-team call sites write a raw email there, so `delete_user_data` strips it (`_redact_audit_context_pii`, replacing the key with `<key>_redacted: true`) per IMPLEMENTATION_SPEC §9.2 "anonymize audit records". That UPDATE is the ONE documented exception to "no UPDATE/DELETE on audit_logs"; extend `_AUDIT_CONTEXT_PII_KEYS` when a new audit context carries PII. `actor_role` is a plain-TEXT **snapshot** (`'system'` valid for cron/worker, `actor=None`). `audit_log(actor=None, actor_role=None)` raises `ValueError`.
- Slugs dotted-lowercase-verb-past; reserved prefixes `resume.*` `application.*` `job.*` `consent.*` `user.*` `admin.*` `auth.*` `employer.*` (table in spec §4).
- **structlog FIRST, `audit_log()` SECOND, then side-effect** (canonical `jobify_api.routes.applications:recruiter_download_application_resume`). structlog → Fluent Bit → Elasticsearch is the live channel; the DB row is durable — complementary.

## Consent + channel prefs — spec `2026-05-29-consent-channel-prefs-design.md`

- **`user_consents` = state; `audit_logs` = history.** `set_consent(...)` is the ONLY path writing a `consent.*` audit row (same txn); no-op flips write none. Don't hand-write consent audit rows.
- **`ON DELETE CASCADE` on `user_id`** (opposite of audit_logs) — consent vanishes with the user; history survives via `actor_user_id SET NULL`.
- **Eager seeding at signup** — `_upsert_identity` calls `seed_default_consents(...)`; later reads are plain SELECTs. Default changes affect only NEW signups. `email_transactional` defaults `true` — signup UI MUST notify the user.
- **Sweep gate:** `sweep_notifications._dispatch_one` checks consent between user-load and dispatch. No consent → `status=CANCELLED`, terminal (re-grant doesn't resurrect). `get_consent` raising `LookupError` (seeding skipped — pre-P4-B / DSR-cascaded) → falls back to `DEFAULT_CONSENTS[scope]`; backfill `jobify-seed-consents`. Inbox excludes `CANCELLED` + `FAILED`.
- Scopes are `StrEnum` at the boundary, TEXT in DB; reserved scopes ship default `false` so impls skip an enum migration.
- **Adding a Postgres enum value** can't share a txn with other DDL. Try `op.get_context().autocommit_block()` first; our async setup trips on `_in_external_transaction` — Alembic 0014's `bind.commit()` + `run_async(...)` is a **documented exception, DO NOT copy unprompted** (document the error first).

## LLM parser — spec `2026-08-01-llm-resume-parsing-design.md`

- **LLM parser (spec `2026-08-01-llm-resume-parsing-design.md`):** `parser/llm_parser.py` is the ONLY module importing `google.genai` in the parser package — never re-export `GeminiResumeParser` from `parser/__init__` (would drag genai into every import). `thinking_budget=0` + `max_output_tokens=8192` are load-bearing (explainer starvation precedent). `LlmParserError(ParserError)` = post-extraction LLM failure; `FallbackResumeParser` catches it (and any non-ParserError) → library fallback + `parse.llm-failed` log; plain extraction `ParserError`s propagate (permanent for any parser). **Debug logging is PII-constrained:** the model's response body restates the applicant's resume, so failures log `_raw_shape(raw)` (length, JSON-validity, error offset, which *schema* keys came back, count of unknown keys) — never the body, not even truncated. Unknown key names are counted, never logged: a malformed response can put content in key position. Same reasoning as the exception messages, which carry field names only.

Two eval lanes: CI = library at 0.85 (deterministic); acceptance 0.90 = on-demand LLM lane, record committed at `core/data/parse_eval/LLM_EVAL_REPORT.md` — refresh it in the same commit as any prompt/model/dataset change (numbers live there, not here). Eight fields are scored; only the original four (name/email/phone/skills) feed `overall`, so 0.85/0.90 keep their meaning — `languages`/`experience`/`education`/`certifications` gate the LLM lane individually (`LLM_PER_FIELD_FLOORS`, set 2026-09-08 from the prompt-v3 baseline) and are print-only on the library lane (specs `2026-09-07-extraction-yardstick-design.md`, `2026-09-08-extraction-prompt-v3-design.md`). Parser default is `gemini-3.1-flash-lite` (beat 2.5 Flash on both sets at ~1/3 the output price); the explainer stays on `gemini-2.5-flash` because the lite model invents facts in explanations — don't "align" the two models without re-running the explainer sample in the report's appendix. Skills rule (product decision 2026-09-07, applied to every gold file): a noun phrase naming a competency/tool/domain the resume states, any vocabulary, verbatim at the resume's granularity; human languages → `languages`; no trait adjectives. The test prints a per-example token diff for every set field so each FP can be checked against the resume text — a token absent from the text is an invented entry, the one error class the gate exists to catch. `JOBIFY_PARSE_EVAL_MODELS=a,b` compares models in one run (first is gated). A local-only REAL set (`sample_resume/`, gitignored PII) is scored when present — aggregate counts only, never token diffs. Key failures: a 429 whose body says "prepayment credits are depleted" = top up the prepaid project (fails fast, ~1 min to propagate); a 403 = key from a project without billing, a top-up won't fix it. **There is ONE call shape — interactive.** `parse_texts_batch` (Gemini Batch API) was removed 2026-08-15: no caller once the eval lane moved to paced interactive, and never verified live (batch returned FAILED_PRECONDITION on free tier, then 403). In git history if bulk re-parse becomes real — verify it against the real API before trusting it; its only coverage was mocked.

## Match explanations — specs `p2.4` + `2026-05-28-llm-match-explanations-design.md`

The explainer modules live here (`jobify` integrations); they are invoked inline by the score workers (see `worker/CLAUDE.md`).

- **`matches.explanation` JSONB** `{fit, caveat, generator, generator_version}`, nullable. Generated inline in both score workers.
- **`MatchExplainer` Protocol** routes two impls; workers call `await get_match_explainer().explain(ctx)`, call site unchanged. **`explain()` NEVER raises** — scoring is never failed by the explainer.
- **`TemplatedExplainer`** (`explainer.py`, wraps pure `templated_explanation()`) deterministic. **`GeminiMatchExplainer`** (`llm_explainer.py`) surfaced-only (if `ctx.total < ctx.threshold` returns templated, no Gemini); any failure logs `explain.llm-failed` (with `raw_text`) + falls back to templated.
- **`thinking_budget=0` is load-bearing** in the explainer's `GenerateContentConfig` — gemini-2.5 thinks by default and thought tokens count against `max_output_tokens`; with the 200 cap, thinking starved the output and EVERY explain silently fell back to templated (the never-raise contract hides it). Watch `generator` in stored explanations, not just error logs.
- **Selection:** `JOBIFY_MATCH_EXPLAINER` = `"llm"` (default, Gemini) | `"templated"` (dev fallback, no `JOBIFY_GEMINI_API_KEY`). Model `JOBIFY_MATCH_EXPLAINER_MODEL` (`gemini-2.5-flash`). Factory `get_match_explainer()` lazy-singleton. **`explainer.py` does NOT import `google.genai`** (separate module; factory does `from google import genai` lazily). `patched_match_explainer` mirrors the embedding fixture (three modules + cache).
- **`GENERATOR_VERSION` bumps on semantic template/prompt change** — flag template/prompt edits.

## Parse F1 quality gate

- **Gold dataset `core/data/parse_eval/`** (`<id>.txt` + `<id>.expected.json`, all eight fields); raw text (PDF/DOCX extraction bypassed — gate measures parser heuristics). Structured lists score by normalised exact match on a key (`company|title`, `institution|degree`, `name`) — gold is authored to the resume's own wording; no fuzzy matching by design.
- **`uv run pytest -m eval`** → `test_library_parser_meets_quality_gate` → `jobify.eval.parse_f1.eval_gold_dataset()`. CI runs it (`lint-types-unit-eval`, no DB) before integration.
- **Gate** (spec §13 P1): macro-F1 ≥ 0.85; floors `email ≥ 0.95`/`phone ≥ 0.85`/`name ≥ 0.70`/`skills ≥ 0.75`. **Only those 4 fields gate** (others print only). Set-skills F1 counts FPs (measures `_extract_skills` over-match drift).
- New gold example: drop a pair with the next id, re-run `-m eval -v -s`; if it tanks a floor, fix the expectation or document the limitation.
- **20 examples (001-020)** — 009-020 are deliberately hard (mangled two-column text, unconventional headers, non-tech vocabularies, name mid-header). `_extract_certifications` requires the literal word "certif\*" — a "PAPERS & BADGES"-style header with real credentials scores zero on that (non-gated) field. **`_extract_skills` matches on TOKEN BOUNDARIES, not substring containment** (fixed 2026-08-15): per-entry lookarounds anchored only on the side whose own edge is alphanumeric — deliberately not `\b…\b`, which breaks entries ending in `+`/`#` (`c++`, `c#`) by demanding a word char after the punctuation. Plus occurrence-based nesting suppression ("Spring Boot" doesn't also report "spring"; a resume writing both "Postgres" and "PostgreSQL" keeps both). Took skills FP 47→3, F1 0.795→0.883, overall 0.904→0.927 with TP/FN unchanged. Full list in `core/data/parse_eval/000_README.md`'s "Documented limitations" section.

## Seeding — spec `2026-05-20-p2.0-jobs-and-seeding-design.md`

CLI entrypoint `jobify-seed-jobs` AND its loader logic live in `api/src/jobify_api/scripts/seed_jobs.py`; only the 44-line data fixture (`core/data/sample_jobs.json`) lives here.

- **`employers`/`jobs` via CLI** (`uv run jobify-seed-jobs` reads `core/data/sample_jobs.json`, upserts), not migrations. Idempotency: `employers.name_norm` (DB partial-UNIQUE) + `(jobs.employer_id, lower(jobs.title))` (script-only). JSON uses `posted_days_ago: int` (→ `now() - timedelta`) so it doesn't age.
- **Updates preserve human state:** `employers.name` never overwritten; `verified_at` set only when `NULL`.
- **`_apply_in_session(session, payload, report)` is the test seam** (CLI's `_apply()` opens its own engine; tests pass the savepoint session). It stages one durable `jobify.embed_job` outbox event per inserted/updated job in the same transaction.
- **Drift guard** `test_loader_against_sample_jobs_json` asserts `employers==10, jobs==27` — update in the same commit.
