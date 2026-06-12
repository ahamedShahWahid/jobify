"""Composition: vector + structured → weighted total with threshold flag."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from jobify.scoring.structured import structured_score
from jobify.scoring.vector import vector_score


class TransientScoringError(Exception):
    """Raised for transient DB hiccups inside a score worker — autoretry target.

    Permanent failures (missing entities, malformed inputs) are logged and
    return without raising; they should not retry.
    """


@dataclass(frozen=True)
class MatchScore:
    vector: float
    structured: float
    total: float
    components: dict[str, float]
    crosses_threshold: bool


def score_match(
    *,
    applicant_embedding: list[float],
    job_embedding: list[float],
    applicant_locations: list[str],
    applicant_years: Decimal | None,
    applicant_expected_ctc: Decimal | None,
    job_locations: list[str],
    job_min_exp_years: int,
    job_max_exp_years: int,
    job_ctc_min: Decimal | None,
    job_ctc_max: Decimal | None,
    vector_weight: float,
    threshold: float,
) -> MatchScore:
    """Compose vector + structured into a single weighted total."""
    v = vector_score(applicant_embedding, job_embedding)
    s, components = structured_score(
        applicant_locations=applicant_locations,
        applicant_years=applicant_years,
        applicant_expected_ctc=applicant_expected_ctc,
        job_locations=job_locations,
        job_min_exp_years=job_min_exp_years,
        job_max_exp_years=job_max_exp_years,
        job_ctc_min=job_ctc_min,
        job_ctc_max=job_ctc_max,
    )
    structured_weight = 1.0 - vector_weight
    total = vector_weight * v + structured_weight * s
    return MatchScore(
        vector=v,
        structured=s,
        total=total,
        components=components,
        crosses_threshold=total >= threshold,
    )
