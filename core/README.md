# Jobify Core

Shared domain package (`jobify`). This is a library depended on by the FastAPI service (`jobify_api`) and the Celery worker (`jobify_worker`).

## What's inside

- **Database**: SQLAlchemy models, Alembic migrations (`core/src/jobify/db/migrations/`), schema (`jobify` namespace)
- **Shared settings contracts**: minimal database/logging configuration for migrations and tooling
- **Integrations**: storage, resume parser, Gemini embeddings, email templates, scoring, LLM explainer
- **Domain logic**: consent/channel prefs, DSR export/delete, audit logs, durable outbox primitives
- **Assets**: email templates (`core/emails/`), parse quality-gate gold dataset (`core/data/parse_eval/`), sample jobs fixture (`core/data/sample_jobs.json`)

## Running migrations

Alembic config lives in `core/alembic.ini`. From the **repo root**:

```bash
cd core && uv run alembic upgrade head
```

(Or pass `--env-file=.env` if running from outside the root: `cd core && uv run --env-file=../.env alembic upgrade head`.)

New migration:

```bash
cd core && uv run alembic revision -m "describe the change"
# Edit the generated file under core/src/jobify/db/migrations/versions/
cd core && uv run alembic upgrade head
```

Hand-written migrations only — autogenerate is off.

## Running the API or worker

See `api/README.md` (how to run the FastAPI service) and `worker/README.md` (how to run the Celery daemon).

## Running tests

From the **repo root**:

```bash
uv run pytest -v   # full suite
uv run pytest -v -m "not integration and not eval"   # unit only
uv run pytest -v -m integration   # integration (requires Postgres)
uv run pytest -v -m eval   # parse quality gate
```

For lint/format/type-check, see the repo root CLAUDE.md.
