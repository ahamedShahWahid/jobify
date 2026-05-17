"""Uvicorn entrypoint.

Run locally:
    uv run uvicorn kpa.main:app --reload --port 8000
"""

from __future__ import annotations

from kpa.app_factory import create_app

# create_app() runs at import time. Required env vars (KPA_ENV, KPA_SERVICE_NAME)
# must be set before this module is imported. If a future task adds async
# resources (DB pools, etc.), wire them through FastAPI lifespan events instead
# of doing setup here.
app = create_app()
