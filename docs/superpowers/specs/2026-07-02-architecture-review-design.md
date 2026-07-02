# Whole-Repo Architecture Review — Design

**Date:** 2026-07-02
**Status:** Approved
**Deliverable:** `docs/architecture-review-2026-07.md` (assessment + prioritized roadmap)

## Goal

Review the architecture and code structure of the entire repo — backend uv
workspace (`core`, `api`, `worker`, `tests`), Flutter client (`app/`), and the
unified React web app (`frontend/`) — and produce a written assessment with a
prioritized roadmap of recommended structural changes. This review produces a
**document, not code changes**; any roadmap item the user picks up later gets
its own spec → plan → implementation cycle.

## Evaluation lens

**Near-term shipping velocity.** The repo is an early-stage MVP built by one
developer plus Claude. Every judgment is made against the question: *does this
structure make the next five slices faster or slower to ship safely?*
Consequences:

- Over-engineering (ceremony that doesn't pay for itself at this team size) is
  flagged as harshly as under-engineering.
- "Industry best practice at scale" is not the bar; recommendations like
  service extraction or heavyweight abstraction layers are anti-recommendations
  unless a concrete near-term pain justifies them.
- Existing guardrails (OpenAPI snapshot pin, contract tests, soft-delete
  coverage tests) are judged on payoff-per-maintenance, not on principle.

## Rubric

The same six-point lens is applied to every surface:

1. **Dependency direction & boundaries** — `core` must not import from
   `api`/`worker`; clients must not re-implement backend logic; every unit
   should have an answer to "what does it do / how do you use it / what does
   it depend on."
2. **Cohesion & size** — files or modules grown past what one edit can safely
   hold; mixed responsibilities; files that force whole-file context loads for
   small changes.
3. **Duplication** — within a package, and the expensive cross-surface kind:
   the same concept hand-maintained in backend schemas, Dart DTOs, and TS
   types.
4. **Over-engineering** — abstractions, indirection, or process artifacts that
   cost more to maintain than they return at current team size.
5. **Under-engineering** — missing seams or guards that will make upcoming
   slices measurably slower or riskier.
6. **Docs-vs-code drift** — each package's `CLAUDE.md` claims checked against
   the actual code; stale invariants are findings.

## Method

1. **Parallel deep-read.** Five read-only explorer subagents, one per surface:
   `core/` (incl. migrations), `api/` + `tests/`, `worker/`, `app/`,
   `frontend/`. Each receives the rubric verbatim and returns: a structure
   map, findings tagged with severity (**blocker / friction / nit**) and
   fix-effort (**S / M / L**) citing concrete files, and drift notes against
   its package `CLAUDE.md`.
2. **Cross-cutting synthesis (main session).** The seams no single explorer
   can see: the API contract flow (OpenAPI snapshot → hand-written Dart and TS
   DTOs), soft-delete invariant enforcement across layers, the
   parse → embed → score pipeline boundaries, auth/consent/DSR coverage as
   tables get added, and duplication across the three client surfaces.
3. **Verification discipline.** Explorer findings are leads, not conclusions.
   Every finding that makes the report is re-verified by the main session
   reading the cited files first-hand. An explorer that stalls or returns thin
   results is replaced by a direct read of that package.

## Deliverable structure

`docs/architecture-review-2026-07.md`, five sections:

1. **Verdict** — one-paragraph overall assessment.
2. **What's working** — named explicitly so good structure doesn't get churned
   by future refactors.
3. **Findings** — severity-ranked, each citing real files/paths.
4. **Roadmap** — prioritized recommendations; each carries size (S/M/L),
   payoff stated in velocity terms, and the cost of skipping it.
5. **Non-recommendations** — tempting changes that should explicitly *not* be
   made at this stage, with reasons.

## Out of scope

- No code, config, or migration changes as part of this review.
- No re-litigating shipped product decisions (BRD scope, Flutter-over-RN);
  only structural consequences are in scope.
- Roadmap items are recommendations only — each needs its own approval and
  spec → plan cycle before implementation.
