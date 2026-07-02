# Whole-Repo Architecture Review — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task in the MAIN session. Steps use checkbox (`- [ ]`) syntax for tracking. **Do not delegate Tasks 3–5 to subagents** — the spec (`docs/superpowers/specs/2026-07-02-architecture-review-design.md`) requires synthesis and finding-verification to happen first-hand in the main session.

**Goal:** Produce `docs/architecture-review-2026-07.md` — a whole-repo architecture assessment with a prioritized roadmap, judged on near-term shipping velocity.

**Architecture:** Five parallel read-only explorer agents (one per surface) apply a shared rubric and return cited findings; the main session then reads the cross-surface seams itself, re-verifies every candidate finding against the actual files, and writes the report.

**Tech Stack:** Agent tool (Explore agent type), git; no code changes anywhere.

## Global Constraints

- **Read-only review**: no file in `core/`, `api/`, `worker/`, `tests/`, `app/`, `frontend/`, or `scripts/` is created or modified. The only files this plan writes are the report and this plan's checkbox updates.
- **Lens (verbatim from spec):** near-term shipping velocity — "does this structure make the next five slices faster or slower to ship safely?" Over-engineering is flagged as harshly as under-engineering.
- **Severity vocabulary:** `blocker` (actively causing bugs or will break the next slice) / `friction` (makes every slice slower or riskier) / `nit` (cosmetic). **Effort:** `S` / `M` / `L`.
- **Every reported finding must cite real files the main session has personally read.** Explorer output is leads only.
- **Branch:** all commits on `architecture-review` (already off `origin/main` @ ddc33f3).
- **Deliverable path:** `docs/architecture-review-2026-07.md` — five sections: Verdict / What's working / Findings / Roadmap / Non-recommendations.

---

### Task 1: Dispatch the five explorers in parallel

**Files:**
- Create: none (agent dispatch only)

**Interfaces:**
- Produces: five markdown result blocks (structure map / findings / drift notes / what's working), consumed by Tasks 2–4.

- [ ] **Step 1: Dispatch all five agents in ONE message** (subagent_type `Explore`, default background mode). Each prompt is the shared template below with the `SURFACE BLOCK` substituted.

Shared prompt template (use verbatim, substituting `{{SURFACE BLOCK}}`):

```text
You are reviewing one surface of the Jobify repo (/Users/ahamadshah/ahamed_personal/jobify)
as part of a whole-repo architecture review. READ-ONLY — do not edit anything.

Context: Jobify is an early-stage placement-platform MVP built by one developer plus
Claude. Evaluation lens: NEAR-TERM SHIPPING VELOCITY — for every judgment ask "does this
structure make the next five feature slices faster or slower to ship safely?"
Over-engineering (ceremony that doesn't pay for itself at this team size) is as much a
finding as under-engineering. "Industry best practice at scale" is NOT the bar.

{{SURFACE BLOCK}}

Apply this six-point rubric:
1. Dependency direction & boundaries — core must not import from api/worker; clients must
   not re-implement backend logic; each unit should answer "what does it do / how do you
   use it / what does it depend on".
2. Cohesion & size — files/modules grown past what one edit can safely hold; mixed
   responsibilities; files that force whole-file context loads for small changes.
3. Duplication — within the surface, and note anything hand-maintained here that mirrors
   another surface (schemas/DTOs/types/constants) for the cross-cutting pass.
4. Over-engineering — abstractions, indirection, or process artifacts costing more than
   they return at current team size.
5. Under-engineering — missing seams/guards that will make upcoming slices slower or riskier.
6. Docs-vs-code drift — check every claim in the surface's CLAUDE.md (and README where
   named below) against the actual code; stale claims are findings.

Return AS YOUR FINAL MESSAGE, raw markdown, exactly these four sections:
## Structure map
10–20 lines: directories, one-line responsibilities, dependency arrows.
## Findings
Ranked, max 10. Each: `[severity: blocker|friction|nit] [effort: S|M|L] [rubric #]` +
exact file paths (line numbers where useful) + 2–4 sentences on the velocity impact.
Severity: blocker = actively causing bugs or will break the next slice; friction = makes
every slice slower/riskier; nit = cosmetic. Cite ONLY files you actually read — no
generic advice.
## Drift notes
CLAUDE.md/README claims that don't match the code, with the claim quoted and the
contradicting file cited.
## What's working
3–6 structural things worth preserving, with file citations.
```

The five `SURFACE BLOCK` substitutions:

1. **core** —
```text
Your surface: core/ — the `jobify` domain package (core/src/jobify/**, including
db/migrations/versions/). Read core/CLAUDE.md and audit its claims. Pay attention to:
db/models.py is 954 lines (evaluate whether it still holds as one file); the soft-delete
model and its Annotated types; the integrations/ layout (storage, parser, embeddings,
notifications); why the bare Celery app lives in core while tasks live in worker/ —
evaluate that split; the seeding CLI; consent/ audit/ eval/ scoring/ observability/
subpackages and whether their boundaries are real.
```

2. **api + tests** —
```text
Your surface: api/ (jobify_api FastAPI service: app factory, settings, middleware, auth/,
dsr/, employers/, routes/ incl. the routes-as-packages layout) AND tests/ (unit/,
integration/, eval/, conftest.py, tests/unit/openapi_snapshot.json). Read api/CLAUDE.md
and tests/CLAUDE.md and audit their claims. Pay attention to: route package structure
(routes/admin, routes/employers, routes/jobs) vs top-level api/src/jobify_api/employers —
is the split coherent?; middleware and error-handling wiring; the conftest layering, the
three HTTP clients, savepoint isolation, markers; whether the OpenAPI-snapshot pin +
contract tests pay their maintenance cost for a solo dev; test-to-code distance (tests at
repo root, code in three packages).
```

3. **worker** —
```text
Your surface: worker/ — jobify_worker Celery daemon (tasks/, runtime singletons, worker
entry point). Read worker/CLAUDE.md and worker/README.md and audit their claims. Pay
attention to: the core-owns-celery-app / worker-owns-tasks split (dispatch by task name
via jobify.celery_app.enqueue) — evaluate whether this indirection pays off; runtime
singleton wiring; task boundaries for parse, embed, score, sweep_notifications; how
worker code shares DB access/models with core; error handling and retry semantics in
tasks (silent-failure risk).
```

4. **app (Flutter)** —
```text
Your surface: app/ — the Flutter client (lib/core, lib/data, lib/presentation, test/).
Read app/CLAUDE.md and audit its claims. Pay attention to: the layering — lib/ has
core/data/presentation but NO lib/domain directory; project docs describe "Pragmatic
Clean Architecture (data/domain/presentation)" — verify what the real layering is and
whether the docs drift; hand-written DTOs vs the backend contract (how they'd be kept in
sync); Riverpod provider/controller patterns and keepAlive usage; presentation/ has ~17
feature folders — assess cohesion and any shared-widget sprawl; test structure vs lib
structure.
```

5. **frontend (React)** —
```text
Your surface: frontend/ — unified Vite + React + TS app (src/shared, src/sites, the three
HashRouter surfaces: / applicant, /employers marketing, /console admin+recruiter ops).
Read frontend/CLAUDE.md and frontend/README.md and audit their claims. Pay attention to:
the sites/ split vs shared/ — what's duplicated across the three surfaces that should be
shared (API clients, types, auth); hand-written TS types vs the backend contract; the
shared token layer (src/shared/styles/tokens.css) and theme wiring; component size and
route-file cohesion; whether frontend/styleguide/ (no build step) is live or dead weight.
```

- [ ] **Step 2: Record the five agent IDs** in the session (for SendMessage follow-ups if any return is thin).

---

### Task 2: Collect results and gap-fill

**Files:**
- Create: none

**Interfaces:**
- Consumes: the five explorer result blocks.
- Produces: a consolidated candidate-findings list (in-session), each entry keyed `surface / severity / effort / files / claim`.

- [ ] **Step 1: As each agent completes, check its output has all four sections and ≥3 cited findings.** An agent that stalled, died, or returned generic/uncited output is NOT retried blindly: first send one SendMessage follow-up asking for the missing section; if still thin, the main session direct-reads that surface itself (structure listing + the package CLAUDE.md + the 5 largest files by `wc -l`) and writes its own findings for that surface.
- [ ] **Step 2: Merge the five outputs into one candidate list**, dedup cross-surface repeats (the same DTO-duplication finding will likely arrive from api, app, and frontend — merge into one cross-cutting candidate), preserving every file citation.

---

### Task 3: Cross-cutting synthesis (main session, first-hand)

**Files:**
- Create: none

**Interfaces:**
- Consumes: candidate list from Task 2.
- Produces: cross-cutting candidate findings that no single explorer could see.

- [ ] **Step 1: Contract flow.** Read `tests/unit/openapi_snapshot.json` structure (paths/schemas count, not every line), then locate the client mirrors:

```bash
grep -rln "fromJson" app/lib/data --include="*.dart" | head -20
grep -rn "interface\|type " frontend/src/shared/api frontend/src/sites --include="*.ts" -l | head -20
```

Judge: how many hand-maintained copies of each wire schema exist, what actually catches drift today (snapshot pin? DTO round-trip tests? nothing?), and whether the sync cost is the top velocity tax or acceptable at current size.

- [ ] **Step 2: Soft-delete invariant enforcement.** Read `core/src/jobify/db/models.py` Annotated types + the soft-delete coverage test named in `docs/superpowers/specs/` / `tests/`:

```bash
grep -rn "deleted_at" tests/unit --include="*.py" -l
grep -rn "outerjoin\|joinedload" worker/src api/src --include="*.py" | head -20
```

Judge: is the invariant enforced by structure (types/tests) or by convention (per-query discipline) — the preferences-join lesson (worker soft-delete ON-clause) says where to look.

- [ ] **Step 3: Pipeline seams.** Trace parse → embed → score → notify across the core/worker boundary: read `worker/src/jobify_worker/tasks/` entry points and the `jobify.celery_app.enqueue` call sites:

```bash
grep -rn "enqueue(" core/src api/src worker/src --include="*.py"
```

Judge: is dispatch-by-string-name a clean seam or an ungreppable indirection; where would a new task type have to touch.

- [ ] **Step 4: Cross-client duplication.** Compare how the SAME feature (applications, or preferences) is implemented in `app/lib/data` + `app/lib/presentation` vs `frontend/src/sites` — read one feature end-to-end on each side. Judge whether the three-surface frontend + Flutter split creates a per-slice cost of 3× UI work, and whether anything structural (shared constants, enum wire values) is copy-drifting.

- [ ] **Step 5: PII-table growth path (auth/consent/DSR).** Read the DSR contract-pin test and the consent wiring:

```bash
grep -rn "class.*Base\|__tablename__" core/src/jobify/db/models.py | wc -l
grep -rln "export\|erase\|delete" api/src/jobify_api/dsr tests/unit | head -10
```

Judge: when the next slice adds a PII-bearing table, how many places must the developer remember to touch (DSR export, DSR delete, consent, audit, contract-pin test) — and is that enforced by a test that fails loudly (the known `kpa-dsr-new-pii-table` lesson) or by memory alone.

- [ ] **Step 6: Workspace/root hygiene.** Read root `pyproject.toml`, `scripts/`, `WORKFLOW.md`, `IMPLEMENTATION_SPEC.md` headers; note `keys.txt` (known gitignored secrets scratch), `INSTALLATION.md` + `flutter-app-state.png` (untracked strays), `var/`. Judge: repo-root clutter and whether the doc set (CLAUDE.md × 7, READMEs, 20 specs) has a clear ownership story or is starting to overlap.

---

### Task 4: Verify every candidate finding first-hand

**Files:**
- Create: none

**Interfaces:**
- Consumes: merged candidate list (Tasks 2–3).
- Produces: the final verified findings list with severity/effort confirmed.

- [ ] **Step 1: For each candidate finding, open the cited file(s) with Read** at the cited lines. Confirm the claim is true as stated. Findings whose citations don't hold are dropped; findings that are true-but-overstated get their severity downgraded with a note.
- [ ] **Step 2: For each `blocker`, articulate the concrete failure scenario** (what breaks, on which upcoming slice). A blocker without a failure scenario is demoted to friction.
- [ ] **Step 3: Re-balance the roadmap ordering** by payoff-per-effort under the velocity lens; cheap-S/high-payoff items float to the top regardless of severity label.

---

### Task 5: Write the report and commit

**Files:**
- Create: `docs/architecture-review-2026-07.md`

**Interfaces:**
- Consumes: verified findings list (Task 4).

- [ ] **Step 1: Write `docs/architecture-review-2026-07.md`** with exactly this skeleton:

```markdown
# Jobify Architecture Review — July 2026

**Lens:** near-term shipping velocity (solo dev + Claude). **Scope:** whole repo.
**Method:** 5 rubric-driven explorer agents + main-session verification; every finding below was re-read first-hand.

## 1. Verdict
[one paragraph]

## 2. What's working — keep these
[bulleted, each with file citations; explicitly protected from future churn]

## 3. Findings
[severity-ranked table or list: severity | effort | surface | files | what & why it matters]

## 4. Roadmap
[priority-ordered; each item: name, size S/M/L, payoff in velocity terms, cost of skipping]

## 5. Non-recommendations
[each: the tempting change, why not now, what signal would change the answer]
```

- [ ] **Step 2: Self-check the report** — every finding cites files read in Task 4; no "TBD"; roadmap items each have size + payoff + skip-cost; non-recommendations section is non-empty (the spec demands it).
- [ ] **Step 3: Confirm the working tree touched only the report:**

Run: `git status --short`
Expected: only `?? docs/architecture-review-2026-07.md` (plus the pre-existing untracked `INSTALLATION.md`, `flutter-app-state.png`).

- [ ] **Step 4: Commit**

```bash
git add docs/architecture-review-2026-07.md docs/superpowers/plans/2026-07-02-architecture-review.md
git commit -m "docs: whole-repo architecture review — assessment + roadmap

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 5: Present the report's Verdict + Roadmap to the user** in the final message and ask which roadmap items (if any) to take into their own spec → plan cycles.
