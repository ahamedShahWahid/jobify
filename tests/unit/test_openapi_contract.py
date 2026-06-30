"""OpenAPI snapshot pin — the cross-client contract guard (P0.2).

The FastAPI ``response_model``s are the single source of truth for the wire
contract; the Flutter DTOs (``app/``) and the TypeScript client types
(``frontend/``) both re-encode that shape by hand, with no generation. This test
pins the full generated OpenAPI document to a checked-in snapshot, so ANY change
to a path, method, request/response field, enum, or required-ness shows up as a
reviewable diff in CI — the signal to update the hand-written clients in lockstep.

It is a unit test (no DB): ``create_app().openapi()`` is lazy on the engine, and
the fake-DSN env is set by ``tests/conftest.py:pytest_configure``.

To regenerate after an INTENTIONAL API change:

    JOBIFY_UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest tests/unit/test_openapi_contract.py

then review the diff to ``openapi_snapshot.json`` and update the Flutter/TS clients
to match.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from jobify_api.app_factory import create_app

_SNAPSHOT = Path(__file__).parent / "openapi_snapshot.json"


def _canonical_schema() -> str:
    """The current OpenAPI document as canonical (sorted-key) JSON."""
    return json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"


def test_openapi_schema_matches_snapshot() -> None:
    current = _canonical_schema()

    if os.environ.get("JOBIFY_UPDATE_OPENAPI_SNAPSHOT"):
        _SNAPSHOT.write_text(current)
        return

    assert _SNAPSHOT.exists(), (
        "openapi_snapshot.json is missing — regenerate with "
        "JOBIFY_UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest tests/unit/test_openapi_contract.py"
    )
    expected = _SNAPSHOT.read_text()
    if current == expected:
        return

    # Narrow the failure to which paths/components moved, so the diff is readable.
    cur = json.loads(current)
    exp = json.loads(expected)
    cur_paths = set(cur.get("paths", {}))
    exp_paths = set(exp.get("paths", {}))
    cur_schemas = set(cur.get("components", {}).get("schemas", {}))
    exp_schemas = set(exp.get("components", {}).get("schemas", {}))
    details = {
        "paths_added": sorted(cur_paths - exp_paths),
        "paths_removed": sorted(exp_paths - cur_paths),
        "schemas_added": sorted(cur_schemas - exp_schemas),
        "schemas_removed": sorted(exp_schemas - cur_schemas),
    }
    raise AssertionError(
        "OpenAPI schema drifted from the pinned snapshot "
        f"(path/schema set changes: {details}; field-level changes may also exist). "
        "If intentional, regenerate with "
        "JOBIFY_UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest tests/unit/test_openapi_contract.py "
        "and update the Flutter (app/) + TypeScript (frontend/) clients to match."
    )
