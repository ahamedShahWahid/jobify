# KPA API

FastAPI service for the Khan Placement Agency platform. This directory contains
the backend foundations only — DB layer, auth, and domain code land in
follow-on plans.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/) 0.5+
- Docker (for container builds + future local Postgres/Redis)

## First-time setup

```bash
cd api
uv sync
cp .env.example .env   # adjust as needed
```

## Run locally

The service reads its config from environment variables (all prefixed `KPA_`).
The easiest path is to keep them in `.env` (created in First-time setup above)
and let `uv` load it:

```bash
uv run --env-file=.env uvicorn kpa.main:app --reload --port 8000
```

- `--reload` watches `src/` and restarts the server on code changes. Drop it
  for production-style runs.
- `--port 8000` is the convention; pick anything free if 8000 is in use.

If you'd rather pass vars inline (e.g., CI, one-off overrides), skip `.env`:

```bash
KPA_ENV=local KPA_SERVICE_NAME=kpa-api \
  uv run uvicorn kpa.main:app --reload --port 8000
```

### Verify it's up

```bash
curl -s http://127.0.0.1:8000/health | python -m json.tool
```

Expected response:

```json
{
  "status": "ok",
  "service": "kpa-api",
  "version": "0.1.0",
  "env": "local"
}
```

Other useful URLs while the server is running:

- `http://127.0.0.1:8000/docs` — Swagger UI (interactive API docs)
- `http://127.0.0.1:8000/redoc` — ReDoc (alternative docs view)
- `http://127.0.0.1:8000/openapi.json` — raw OpenAPI schema

Every response (including errors) carries an `X-Request-Id` header — that's
the correlation handle that shows up in the structured logs, so grep for it
when chasing a request through the system.

Stop the server with `Ctrl-C`.

### Run with JSON logs (prod-style)

For Fluent Bit / Elasticsearch compatibility, flip the log format:

```bash
KPA_LOG_FORMAT=json uv run --env-file=.env uvicorn kpa.main:app --port 8000
```

(Inline env vars override anything in `.env`, so this works even with the
default `KPA_LOG_FORMAT=text` in the file.)

## Tests

```bash
uv run pytest -v
```

## Lint, format, type-check

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy
```

## Container build

```bash
docker build -t kpa-api:dev .
docker run --rm -e KPA_ENV=local -e KPA_SERVICE_NAME=kpa-api \
  -e KPA_LOG_LEVEL=INFO -e KPA_LOG_FORMAT=text \
  -p 8000:8000 kpa-api:dev
```

## Configuration

All settings are read from environment variables prefixed `KPA_`:

| Variable           | Required | Default | Purpose                         |
| ------------------ | -------- | ------- | ------------------------------- |
| `KPA_ENV`          | yes      | —       | `local` \| `dev` \| `staging` \| `prod` |
| `KPA_SERVICE_NAME` | yes      | —       | Reported in `/health`           |
| `KPA_LOG_LEVEL`    | no       | `INFO`  | Stdlib log level                |
| `KPA_LOG_FORMAT`   | no       | `text`  | `text` (key=value) or `json`    |

The service refuses to boot if required variables are missing or invalid.

## Project layout

```
api/
├── src/kpa/
│   ├── app_factory.py        # create_app() — middlewares + routes
│   ├── main.py               # uvicorn entry point
│   ├── settings.py
│   ├── middleware/
│   │   ├── request_id.py     # X-Request-Id propagation
│   │   └── error_handler.py  # RFC 7807 problem+json
│   ├── observability/
│   │   └── logging.py        # structlog config
│   └── routes/
│       └── health.py         # GET /health
└── tests/
```
