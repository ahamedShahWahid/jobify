"""Templated match-explanation generator.

Deterministic priority-order rules over score_components and the surrounding
context. Returns a dict with `fit`, `caveat`, `generator`, `generator_version`
fields for storage on matches.explanation.

When the LLM provider decision (BRD §14 #1) is resolved, a MatchExplainer
Protocol will wrap both templated and LLM impls behind a single interface
and the score worker call site stays unchanged.

If the templates change semantically, bump GENERATOR_VERSION.
"""

from __future__ import annotations

from decimal import Decimal

GENERATOR = "templated"
GENERATOR_VERSION = "1"


def templated_explanation(
    *,
    components: dict[str, float],
    vector: float,
    structured: float,
    total: float,
    threshold: float,
    job_title: str,
    job_locations: list[str],
    job_min_exp_years: int,
    job_max_exp_years: int,
    job_ctc_max: Decimal | None,
    employer_name: str,
    applicant_expected_ctc: Decimal | None,
    applicant_locations: list[str],
) -> dict[str, str]:
    loc = components.get("location", 0.5)
    exp = components.get("exp", 0.5)
    ctc = components.get("ctc", 0.5)

    overlap_loc = _location_for_message(job_locations, applicant_locations)
    remote = "remote" in {x.strip().lower() for x in (job_locations + applicant_locations)}

    # --- fit string (priority order) ---
    if total < threshold:
        fit = "Lower-confidence match - surfaced for breadth."
    elif loc >= 0.9 and exp >= 0.9 and ctc >= 0.9:
        fit = f"Strong match: {job_title} in {overlap_loc} " f"aligns with your experience level."
    elif loc >= 0.9 and exp >= 0.9:
        fit = f"Good location and seniority fit for {job_title} in {overlap_loc}."
    elif remote:
        fit = f"Remote-friendly match for {job_title} at {employer_name}."
    else:
        fit = f"Possible match for {job_title} based on your skill profile."

    # --- caveat string (first weakness wins) ---
    if exp < 0.6:
        caveat = (
            f"Experience band: this role asks for "
            f"{job_min_exp_years}-{job_max_exp_years} years."
        )
    elif (
        ctc < 0.6
        and applicant_expected_ctc is not None
        and job_ctc_max is not None
        and applicant_expected_ctc > job_ctc_max
    ):
        caveat = "Compensation may be below your expectation."
    elif loc == 0.0:
        caveat = "Location mismatch - neither side lists overlap or remote."
    else:
        caveat = ""

    return {
        "fit": fit,
        "caveat": caveat,
        "generator": GENERATOR,
        "generator_version": GENERATOR_VERSION,
    }


def _location_for_message(job_locs: list[str], applicant_locs: list[str]) -> str:
    """Return the first overlapping location for display, or the first job
    location. Case-insensitive match, but preserves casing from the job side."""
    if not job_locs:
        return "your preferred location"
    a_lower = {x.strip().lower() for x in applicant_locs}
    for loc in job_locs:
        if loc.strip().lower() in a_lower:
            return loc
    return job_locs[0]
