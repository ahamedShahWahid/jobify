"""Seed employers and jobs from a JSON fixture (idempotent).

Run via:
    uv run python -m kpa.scripts.seed_jobs [--from PATH] [--dry-run]
    uv run kpa-seed-jobs [--from PATH] [--dry-run]

Behavior:
1. Pydantic-validate the JSON. Any error → exit 2; nothing written.
2. Open one session against the engine in app_factory.
3. Upsert employers by ``name_norm``; then upsert jobs by
   ``(employer_id, lower(title))``. One COMMIT (or ROLLBACK on --dry-run).
4. Log row counts on completion.

Exit codes: 0 success, 2 validation, 3 DB error.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import structlog
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

_log = structlog.get_logger(__name__)

_DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parents[3] / "data" / "sample_jobs.json"


# --- Pydantic input models ---------------------------------------------------

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
Location = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
GST = Annotated[str, StringConstraints(strip_whitespace=True, min_length=15, max_length=15)]


class EmployerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    gst: GST | None = None
    verified: bool = False


class JobInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employer_name: Name
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]
    description: NonEmptyStr
    locations: list[Location] = Field(default_factory=list, max_length=10)
    min_exp_years: int = Field(ge=0, le=50)
    max_exp_years: int = Field(ge=0, le=50)
    ctc_min: float | None = Field(default=None, ge=0)
    ctc_max: float | None = Field(default=None, ge=0)
    status: str = "open"
    posted_days_ago: int = Field(ge=0, le=3650)

    @model_validator(mode="after")
    def _validate_ranges(self) -> JobInput:
        if self.max_exp_years < self.min_exp_years:
            raise ValueError("max_exp_years must be >= min_exp_years")
        if (
            self.ctc_max is not None
            and self.ctc_min is not None
            and self.ctc_max < self.ctc_min
        ):
            raise ValueError("ctc_max must be >= ctc_min")
        if self.status not in {"open", "closed"}:
            raise ValueError("status must be 'open' or 'closed'")
        return self


class SeedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    employers: list[EmployerInput]
    jobs: list[JobInput]

    @model_validator(mode="after")
    def _validate_payload(self) -> SeedPayload:
        if self.version != 1:
            raise ValueError(f"unsupported version: {self.version}")
        employer_names = {e.name for e in self.employers}
        for job in self.jobs:
            if job.employer_name not in employer_names:
                raise ValueError(
                    f"job references unknown employer: {job.employer_name!r}"
                )
        return self


# --- Helpers -----------------------------------------------------------------

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Lowercase + collapse internal whitespace + strip — the idempotency key
    for the partial-UNIQUE index on ``employers.name_norm``."""
    return _WHITESPACE_RE.sub(" ", name.strip()).lower()


@dataclass
class SeedReport:
    employers_inserted: int = 0
    employers_updated: int = 0
    jobs_inserted: int = 0
    jobs_updated: int = 0
    dry_run: bool = False

    def as_log_kwargs(self) -> dict[str, int | bool]:
        return {
            "employers_inserted": self.employers_inserted,
            "employers_updated": self.employers_updated,
            "jobs_inserted": self.jobs_inserted,
            "jobs_updated": self.jobs_updated,
            "dry_run": self.dry_run,
        }


# --- IO + entry --------------------------------------------------------------

def _load_and_validate(path: Path) -> SeedPayload:
    raw = json.loads(path.read_text())
    return SeedPayload.model_validate(raw)


async def _apply(payload: SeedPayload, *, dry_run: bool) -> SeedReport:
    raise NotImplementedError("loader landed in a later task")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="seed_jobs",
        description="Seed employers and jobs from a JSON fixture (idempotent).",
    )
    parser.add_argument(
        "--from",
        dest="path",
        type=Path,
        default=_DEFAULT_FIXTURE_PATH,
        help=f"Path to seed JSON. Default: {_DEFAULT_FIXTURE_PATH}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse + validate the JSON, log what would change, do not write.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _log.info("seed.start", path=str(args.path), dry_run=args.dry_run)
    try:
        payload = _load_and_validate(args.path)
    except Exception as exc:  # validation/IO failures
        _log.error("seed.validation-failed", error=str(exc))
        return 2
    try:
        report = asyncio.run(_apply(payload, dry_run=args.dry_run))
    except NotImplementedError:
        # Stub until Task 7; CLI is still usable for --dry-run validation only.
        _log.warning("seed.loader-not-implemented")
        return 0
    except Exception as exc:
        _log.error("seed.db-failed", error=str(exc))
        return 3
    _log.info("seed.complete", **report.as_log_kwargs())
    return 0


if __name__ == "__main__":
    sys.exit(main())
