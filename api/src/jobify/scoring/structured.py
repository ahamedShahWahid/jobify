"""Per-rule structured fits and their aggregate.

Each fit returns 0.0-1.0. Missing-data cases return 0.5 (no signal either way)
rather than 0.0 (anti-signal) — see spec §6.3 design rationale.
"""

from __future__ import annotations

from decimal import Decimal


def location_fit(applicant_locations: list[str], job_locations: list[str]) -> float:
    """1.0 if either side is empty: 0.5 (no signal).

    1.0 if any case-insensitive overlap OR either side includes 'Remote'.
    0.0 if both sides populated with no overlap and no remote on either side.
    """
    if not applicant_locations or not job_locations:
        return 0.5
    a = {loc.strip().lower() for loc in applicant_locations}
    j = {loc.strip().lower() for loc in job_locations}
    if "remote" in a or "remote" in j:
        return 1.0
    return 1.0 if a & j else 0.0


def exp_fit(applicant_years: Decimal | None, job_min: int, job_max: int) -> float:
    """Fit of applicant's years against the job's [min, max] band.

    - In band → 1.0.
    - Over band → linear decay; 0.0 at 2 * job_max.
    - Under band → linear decay (y / job_min); 0.0 at y=0.
    - None → 0.5.
    """
    if applicant_years is None:
        return 0.5
    y = float(applicant_years)
    if job_min <= y <= job_max:
        return 1.0
    if y > job_max:
        if job_max == 0:
            return 0.0
        return max(0.0, 1.0 - (y - job_max) / job_max)
    # y < job_min
    if job_min == 0:
        return 1.0
    return max(0.0, y / job_min)


def ctc_fit(
    applicant_expected: Decimal | None,
    job_min: Decimal | None,
    job_max: Decimal | None,
) -> float:
    """Fit of applicant's expected CTC against the job's [min, max] band.

    - Missing data on either side → 0.5.
    - Within band or under band → 1.0 (applicant happy with less).
    - Over band → linear decay; 0.0 at 1.5 * job_max.
    """
    if applicant_expected is None or (job_min is None and job_max is None):
        return 0.5
    a = float(applicant_expected)
    jmax = float(job_max) if job_max is not None else None
    jmin = float(job_min) if job_min is not None else None
    if jmin is not None and a < jmin:
        return 1.0
    if jmax is not None and a > jmax:
        if jmax == 0:
            return 0.0
        return max(0.0, 1.0 - (a - jmax) / (0.5 * jmax))
    return 1.0


def structured_score(
    *,
    applicant_locations: list[str],
    applicant_years: Decimal | None,
    applicant_expected_ctc: Decimal | None,
    job_locations: list[str],
    job_min_exp_years: int,
    job_max_exp_years: int,
    job_ctc_min: Decimal | None,
    job_ctc_max: Decimal | None,
) -> tuple[float, dict[str, float]]:
    """Return (score, components) — unweighted mean of the three rule fits."""
    components = {
        "location": location_fit(applicant_locations, job_locations),
        "exp": exp_fit(applicant_years, job_min_exp_years, job_max_exp_years),
        "ctc": ctc_fit(applicant_expected_ctc, job_ctc_min, job_ctc_max),
    }
    score = sum(components.values()) / len(components)
    return score, components
