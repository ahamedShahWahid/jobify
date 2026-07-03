# Architecture Review (2026-07) Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all 8 actionable roadmap items from `docs/architecture-review-2026-07.md` (roadmap items #1–#8; item #9, the contract-sync script, is explicitly deferred per the review's own recommendation).

**Architecture:** Each task is an independent, self-contained fix in one subsystem (frontend/api/worker/app/docs). No task depends on another's code (doc-only tasks touch different files than code tasks). Order follows the review's payoff-per-effort roadmap ranking.

**Tech Stack:** React/Vite/TS (frontend), FastAPI/SQLAlchemy (api), Celery (worker), Flutter/Dart (app), Markdown (docs).

## Global Constraints

- Backend CI verbatim (run from repo root before claiming green): `uv run ruff check core/src api/src worker/src tests` · `uv run ruff format --check core/src api/src worker/src tests` · `uv run mypy` · `uv run pytest -v -m "not integration and not eval"` · `uv run pytest -v -s -m eval` · `uv run pytest -v -m integration`.
- App CI verbatim: `dart format --set-exit-if-changed lib test` · `flutter analyze` · `flutter test`.
- Frontend CI verbatim: `npm run build` (= `tsc -b && vite build`) from `frontend/`.
- Decision already made with the user: sweep_notifications gets a real Celery beat schedule (Task 7), not just a descope note.
- Sizing per the review: Tasks 1,2,3,4,5,6 = S; Task 7,8 = M.

---

### Task 1: Fix dead anchor links (finding #1, roadmap #1)

**Files:**
- Modify: `frontend/src/sites/employers/components/Chrome.tsx:75,76,78`
- Modify: `frontend/src/sites/web/components/Chrome.tsx:20,61,62,72`

**Interfaces:** None — pure JSX tag/prop swap, no new exports.

- [ ] **Step 1: Fix employers Chrome.tsx footer (anchors exist on `employers/pages/Landing.tsx`: `#how`, `#showcase`, `#pricing`)**

Replace:
```tsx
            <a href="/#how">How it works</a>
            <a href="/#showcase">Match reasoning</a>
            <Link to="/employers/verify">Get verified</Link>
            <a href="/#pricing">Pricing</a>
```
with:
```tsx
            <Link to="/employers#how">How it works</Link>
            <Link to="/employers#showcase">Match reasoning</Link>
            <Link to="/employers/verify">Get verified</Link>
            <Link to="/employers#pricing">Pricing</Link>
```

- [ ] **Step 2: Fix web Chrome.tsx (anchors exist on `web/pages/Landing.tsx`: `#how`, `#recruiters`)**

In `Masthead()`, replace:
```tsx
          <a href="/#how">How it works</a>
```
with:
```tsx
          <Link to="/#how">How it works</Link>
```

In `Footer()`, replace:
```tsx
            <a href="/#how">How matching works</a>
            <a href="/#recruiters">For recruiters</a>
```
with:
```tsx
            <Link to="/#how">How matching works</Link>
            <Link to="/#recruiters">For recruiters</Link>
```

and replace:
```tsx
            <a href="/#how">About</a>
```
with:
```tsx
            <Link to="/#how">About</Link>
```

(`Link` is already imported in both files — no new import needed.)

- [ ] **Step 3: Verify**

Run: `cd frontend && npm run build`
Expected: builds clean (tsc + vite), no unused-import warnings (Link was already imported/used elsewhere in both files).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/sites/employers/components/Chrome.tsx frontend/src/sites/web/components/Chrome.tsx
git commit -m "fix(frontend): replace raw anchor hrefs with surface-prefixed Link (arch review #1)"
```

---

### Task 2: De-duplicate the role-flip logic (finding #7, roadmap #2)

**Files:**
- Modify: `api/src/jobify_api/routes/employers/core.py`

**Interfaces:**
- Consumes: `flip_to_recruiter(session: AsyncSession, user_id: uuid.UUID) -> None` from `jobify_api.employers.membership` (already exists, does not commit — caller owns the transaction, same as today's inline code).

- [ ] **Step 1: Add the import**

Add to the import block (after the `jobify_api.auth.dependencies` import):
```python
from jobify_api.employers.membership import flip_to_recruiter
```

- [ ] **Step 2: Replace the inline update with the shared helper**

Replace:
```python
    # Role flip: APPLICANT → RECRUITER. Bounded; never demotes ADMIN.
    # No-op for an existing recruiter.
    await session.execute(
        update(User)
        .where(User.id == user.id, User.role == UserRole.APPLICANT)
        .values(role=UserRole.RECRUITER, updated_at=func.now())
    )
```
with:
```python
    # Role flip: APPLICANT → RECRUITER. Delegates to the shared helper so this
    # stays the only inline copy of the flip (see api/CLAUDE.md's `require_applicant`
    # war story for what happens when it's re-inlined instead).
    await flip_to_recruiter(session, user.id)
```

- [ ] **Step 3: Trim now-unused imports**

`func`, `update` (from `sqlalchemy`) and `UserRole` (from `jobify.db.models`) are used nowhere else in this file after Step 2 — confirmed via `grep -n 'func\.\|update(\|UserRole' api/src/jobify_api/routes/employers/core.py` before editing. Change:
```python
from sqlalchemy import func, select, update
```
to:
```python
from sqlalchemy import select
```
and:
```python
from jobify.db.models import Employer, EmployerUser, User, UserRole
```
to:
```python
from jobify.db.models import Employer, EmployerUser, User
```

- [ ] **Step 4: Verify**

Run: `uv run ruff check api/src/jobify_api/routes/employers/core.py && uv run mypy`
Expected: no unused-import errors, no type errors.

Run: `uv run pytest -v -m integration -k employer`
Expected: PASS (existing employer-creation tests exercise this exact path — `POST /v1/employers` flipping APPLICANT→RECRUITER).

- [ ] **Step 5: Commit**

```bash
git add api/src/jobify_api/routes/employers/core.py
git commit -m "refactor(api): route employer creation's role flip through flip_to_recruiter (arch review #7)"
```

---

### Task 3: Batch-fix confirmed doc-drift (finding #4, roadmap #3)

**Files:**
- Modify: `core/CLAUDE.md:53`
- Modify: `api/CLAUDE.md` (App wiring / Middleware sections)
- Modify: `app/CLAUDE.md` (the "ONE documented data→presentation exception" claim)
- Modify: `frontend/README.md:51-54`
- Modify: `frontend/src/sites/web/api/types.ts:3`, `frontend/src/sites/console/api/types.ts:3` (bonus: same stale-path drift class, one-line each, directly cited by the review)

**Interfaces:** None — documentation only.

- [ ] **Step 1: `core/CLAUDE.md` — seed loader location**

Replace:
```
CLI entrypoint `jobify-seed-jobs` lives in the `api` package's scripts; the data + loader logic are here.
```
with:
```
CLI entrypoint `jobify-seed-jobs` AND its loader logic live in `api/src/jobify_api/scripts/seed_jobs.py`; only the 44-line data fixture (`core/data/sample_jobs.json`) lives here.
```

- [ ] **Step 2: `api/CLAUDE.md` — App wiring section mentions all three `app.state` things**

Current text stops at `storage`; `app_factory.py:64-73` also sets `app.state.google_verifier` and adds `MetricsMiddleware`. Replace:
```
`create_app()` builds a fresh app per call (test isolation), owning three `app.state` things: `settings`; `db_engine` + `db_sessionmaker` (single async engine, sets `search_path=jobify` via asyncpg `server_settings` so model code does **not** repeat `schema="jobify"`; disposed on `shutdown` — **don't create your own engine in module scope**); `storage` (a `Storage` protocol impl, currently `LocalFileStorage`). Routes read these via `Depends` (`get_session` in `jobify_api.dependencies`, `get_storage`); tests swap via `app.dependency_overrides`.
```
with:
```
`create_app()` builds a fresh app per call (test isolation), owning four `app.state` things: `settings`; `db_engine` + `db_sessionmaker` (single async engine, sets `search_path=jobify` via asyncpg `server_settings` so model code does **not** repeat `schema="jobify"`; disposed on `shutdown` — **don't create your own engine in module scope**); `storage` (a `Storage` protocol impl, currently `LocalFileStorage`); `google_verifier` (`JwksGoogleIdTokenVerifier`, used by Google sign-in). Routes read these via `Depends` (`get_session` in `jobify_api.dependencies`, `get_storage`); tests swap via `app.dependency_overrides`.
```

- [ ] **Step 3: `api/CLAUDE.md` — Middleware section mentions `MetricsMiddleware`**

Replace:
```
`RequestIdMiddleware` is pure ASGI on purpose: `BaseHTTPMiddleware` wraps the app in an `anyio` task group → asyncpg raises `Future attached to a different loop`. **New middleware must be pure-ASGI.** Request id = uuid4; client `X-Request-Id` honored only if a valid uuid4, else replaced; on every response (incl. errors) as the only log correlation handle. `CORSMiddleware` mounted **after** `RequestIdMiddleware` (outermost). Origins from `JOBIFY_CORS_ALLOW_ORIGINS` (default `http://localhost:8080`); no cookies → `allow_credentials` off. Only web needs it (mobile sends no `Origin`).
```
with:
```
`RequestIdMiddleware` is pure ASGI on purpose: `BaseHTTPMiddleware` wraps the app in an `anyio` task group → asyncpg raises `Future attached to a different loop`. **New middleware must be pure-ASGI.** Request id = uuid4; client `X-Request-Id` honored only if a valid uuid4, else replaced; on every response (incl. errors) as the only log correlation handle. `MetricsMiddleware` is added next (also pure-ASGI, see `jobify_api.middleware.metrics`) — it wraps `RequestIdMiddleware` so it counts every routed request including `HTTPException`/500 responses, but stays inside `CORSMiddleware` so CORS preflight (OPTIONS) short-circuits aren't counted. `CORSMiddleware` mounted **after** both (outermost). Origins from `JOBIFY_CORS_ALLOW_ORIGINS` (default `http://localhost:8080`); no cookies → `allow_credentials` off. Only web needs it (mobile sends no `Origin`).
```

- [ ] **Step 4: `app/CLAUDE.md` — fix "the ONE documented exception" (there are two)**

Replace:
```
- **`AccessTokenHolder`** — mutable singleton bridging dio (below Riverpod) and the app. `dio_provider` depends on `authStateProvider` (presentation) to push `SignedOut` on refresh failure — the ONE documented data→presentation exception.
```
with:
```
- **`AccessTokenHolder`** — mutable singleton bridging dio (below Riverpod) and the app. Both `dio_provider` and `auth_repository_provider` import `authStateProvider` (presentation) to push auth-state changes back up (`SignedOut` on refresh failure; state updates on sign-in/out) — these two files are the documented data→presentation exceptions, not one.
```

- [ ] **Step 5: `frontend/README.md` — design tokens are global, not per-surface**

Replace:
```
## Design tokens

Each surface owns its own CSS-variable token system in `src/sites/<surface>/styles/`.
The static `frontend/styleguide/` is a hand-maintained snapshot of those tokens.
```
with:
```
## Design tokens

Tokens are global, not per-surface: `src/shared/styles/tokens.css` defines every
color/spacing/font variable once on `:root` (light) and `:root[data-theme="dark"]`
(dark). Surfaces consume `var(--token)` — they must not redefine tokens on
`.surface-*`. See `frontend/CLAUDE.md` for the full design-system rules.
The static `frontend/styleguide/` is a hand-maintained snapshot of those tokens.
```

- [ ] **Step 6: Fix the stale package path in both hand-written DTO file headers**

In `frontend/src/sites/web/api/types.ts:3`, replace:
```
 * Source of truth: api/src/jobify/routes/{schemas,feed,jobs,applications,saved_jobs,me}.py.
```
with:
```
 * Source of truth: api/src/jobify_api/routes/{schemas,feed,jobs,applications,saved_jobs,me}.py.
```

In `frontend/src/sites/console/api/types.ts:3`, replace:
```
 * Source of truth: api/src/jobify/routes/{admin,jobs,employers,me}.py.
```
with:
```
 * Source of truth: api/src/jobify_api/routes/{admin,jobs,employers,me}.py.
```

- [ ] **Step 7: Verify**

Doc-only changes — no test suite covers prose. Sanity-check with `git diff` that each replacement lands exactly once and nothing else in the surrounding paragraph was altered.

- [ ] **Step 8: Commit**

```bash
git add core/CLAUDE.md api/CLAUDE.md app/CLAUDE.md frontend/README.md frontend/src/sites/web/api/types.ts frontend/src/sites/console/api/types.ts
git commit -m "docs: fix confirmed CLAUDE.md/README/DTO-header drift across 5 surfaces (arch review #4)"
```

---

### Task 4: Delete the dead `ds-*` CSS primitives (finding #5, roadmap #4)

**Files:**
- Modify: `frontend/src/shared/styles/components.css`
- Modify: `frontend/CLAUDE.md` (Design system → Shared primitives bullet)

**Interfaces:** None. `.ds-theme-switch`/`.ds-theme-switch-btn` (consumed by `shared/theme/ThemeToggle.tsx`) and the dark-mode `.brand-logo` filter rule are kept as-is.

- [ ] **Step 1: Confirm zero consumers one more time (repeat the review's grep before deleting)**

Run: `cd frontend/src && grep -rn 'ds-btn\|ds-card\|ds-input\|ds-badge' sites/`
Expected: no output (zero matches) — if this now returns matches, STOP and re-scope (something started using the dead classes since the review).

- [ ] **Step 2: Delete the unused primitives from `components.css`**

Remove the `/* ─── Button ─── */`, `/* ─── Card ─── */`, `/* ─── Input / Textarea / Select ─── */`, and `/* ─── Badge / Status chip ─── */` sections in full (lines defining `.ds-btn`, `.ds-btn-primary`, `.ds-btn-danger`, `.ds-btn-ghost`, `.ds-btn-sm`, `.ds-card`, `.ds-input`, `.ds-badge` + `.ds-badge-ok/warn/danger/accent`). Keep the file header comment (adjusted, see Step 3), the `/* ─── Theme switch ─── */` block, and the trailing `/* Brand logo on dark surfaces. */` block untouched.

Resulting file:
```css
/* frontend/src/shared/styles/components.css
   Shared component primitives. The button/card/input/badge primitives that
   used to live here were deleted 2026-07 (architecture review): zero
   consumers under src/sites/ ever adopted them, each surface hand-rolls its
   own instead. Only the theme switch below has a real consumer
   (shared/theme/ThemeToggle.tsx) — build 100% on semantic tokens if you add
   another shared primitive here, so it renders correctly in both themes
   without a per-surface override. */

/* ─── Theme switch (3-way segmented: light / dark / system) ──────────────── */
.ds-theme-switch {
  display: inline-flex;
  gap: 2px;
  padding: 2px;
  border: 1px solid var(--line);
  border-radius: 3px;
  background: var(--paper-2);
}
.ds-theme-switch-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.9em;
  height: 1.9em;
  border: 0;
  background: transparent;
  color: var(--ink-faint);
  border-radius: 2px;
  cursor: pointer;
  transition: color 0.15s var(--ease), background-color 0.15s var(--ease);
}
.ds-theme-switch-btn:hover {
  color: var(--ink-soft);
}
.ds-theme-switch-btn.is-active {
  background: var(--panel);
  color: var(--brand-blue);
}
.ds-theme-switch-btn:focus-visible {
  outline: 2px solid var(--brand-blue);
  outline-offset: 1px;
}

/* Brand logo on dark surfaces.
   jobify-logo.svg is a monochrome trace in the brand blue (#0048A8) — legible
   on the light paper, but dark-blue on near-black loses the wordmark + tagline.
   Brighten it in dark mode, mirroring exactly what the --brand-blue token does
   (#0048A8 → #4f8cff). One shared rule covers every surface's .brand-logo;
   light mode is untouched. data-theme is always a concrete light|dark value
   (ThemeProvider resolves "system"), so this is reliable for system-dark too. */
:root[data-theme="dark"] .brand-logo {
  filter: brightness(1.8) saturate(0.9);
}
```

- [ ] **Step 3: Update `frontend/CLAUDE.md`'s Shared primitives bullet**

Replace:
```
- **Shared primitives:** `src/shared/styles/components.css` — `.ds-btn` / `.ds-btn-primary` / `.ds-btn-danger` / `.ds-btn-ghost` / `.ds-btn-sm` / `.ds-card` / `.ds-input` / `.ds-badge` (+`.ds-badge-ok/warn/danger/accent`) / `.ds-theme-switch` (3-way light/dark/system segmented control). 100 % token-driven, render correctly in both themes. Surfaces keep their own scoped variants; these are the canonical baseline.
```
with:
```
- **Shared primitives:** `src/shared/styles/components.css` — currently just `.ds-theme-switch` (3-way light/dark/system segmented control, consumed by `shared/theme/ThemeToggle.tsx`). The button/card/input/badge primitives once here were deleted 2026-07 (zero adopters after PR #44/#45 — each surface hand-rolled its own instead); don't reintroduce a "canonical baseline" speculatively — build one only when a real slice needs to share a component across surfaces.
```

- [ ] **Step 4: Verify**

Run: `cd frontend && npm run build`
Expected: builds clean — no CSS class was referenced anywhere under `sites/`, confirmed in Step 1.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/shared/styles/components.css frontend/CLAUDE.md
git commit -m "chore(frontend): delete unused ds-btn/card/input/badge primitives, keep ds-theme-switch (arch review #5)"
```

---

### Task 5: Correct `IMPLEMENTATION_SPEC.md`'s app-client section (finding #3, roadmap #5)

**Files:**
- Modify: `IMPLEMENTATION_SPEC.md:95-101`

**Interfaces:** None — documentation only.

- [ ] **Step 1: Mark the unbuilt interceptors/codegen as backlog, not shipped**

Replace:
```
### 3.4 API client

`dio` with interceptors:
- Auth: attach access token; on 401, attempt refresh, queue and retry pending requests.
- Trace: send `X-Request-Id` (uuid v4 per request) — server echoes it; used for support tickets.
- Telemetry: timing per endpoint, emit to analytics sink.
- Retry: idempotent GETs only, exponential backoff capped at 3 attempts.

OpenAPI codegen from FastAPI's `/openapi.json` produces typed Dart clients. CI fails if generated client diverges from spec.
```
with:
```
### 3.4 API client

`dio` with interceptors. **Shipped today** (`app/lib/data/api/`): auth (attach access token), refresh-on-401 (single-flight queue/retry), request-id (`X-Request-Id` uuid v4 per request, server echoes it).

**Backlog, not yet built** — no ticket/date attached, revisit if the pain shows up:
- Telemetry interceptor (per-endpoint timing → analytics sink).
- Retry interceptor for idempotent GETs (exponential backoff).
- OpenAPI-to-Dart codegen with a CI diff-gate. The current mitigation is a per-DTO fixture-pin pattern (mirror-comment + literal-JSON round-trip test, see `MeDto`/`JobStatus`/`ApplicationStatus`) — cheaper at today's ~40 paths / 62 schemas; see `docs/architecture-review-2026-07.md` §5 for why full codegen isn't worth it yet.
```

- [ ] **Step 2: Verify**

Doc-only — `git diff IMPLEMENTATION_SPEC.md` sanity check that the section reads correctly and no other section was touched.

- [ ] **Step 3: Commit**

```bash
git add IMPLEMENTATION_SPEC.md
git commit -m "docs: mark IMPLEMENTATION_SPEC's dio retry/telemetry/codegen as backlog, not shipped (arch review #3)"
```

---

### Task 6: Extend the `MeDto` fixture-pin pattern to `JobStatus`/`ApplicationStatus` (finding #9, roadmap #6)

**Files:**
- Modify: `app/lib/data/jobs/job_status.dart`
- Modify: `app/lib/data/jobs/application_status.dart`
- Create: `app/test/unit/data/jobs/job_status_test.dart`
- Create: `app/test/unit/data/jobs/application_status_test.dart`

**Interfaces:**
- Consumes: `JobSummaryDto.fromJson` (`app/lib/data/feed/feed_dto.dart`, field `status` is `JobStatus` with `@JsonKey(unknownEnumValue: JobStatus.unknown)`); `ApplicationDto.fromJson` (`app/lib/data/jobs/jobs_dto.dart`, field `status` is `ApplicationStatus` with the same pattern, field `source` is `ApplicationSource` — needs a valid literal for the fixture).
- Produces: nothing new consumed elsewhere — these are leaf test files.

- [ ] **Step 1: Add the mirror-comment to `job_status.dart`**

Replace the file's current top (no doc comment) — add above `@JsonEnum(alwaysCreate: true)`:
```dart
import 'package:json_annotation/json_annotation.dart';

part 'job_status.g.dart';

/// Mirrors backend `JobStatus` (`core/src/jobify/db/models.py:404`, a `StrEnum`
/// with members `OPEN="open"`/`CLOSED="closed"`). `unknown` is a client-only
/// sentinel for a value the backend hasn't been mapped to yet — DTO fields
/// using this enum must declare `@JsonKey(unknownEnumValue: JobStatus.unknown)`
/// (done today in `JobSummaryDto.status`). Round-trip pinned by
/// `test/unit/data/jobs/job_status_test.dart`.
@JsonEnum(alwaysCreate: true)
enum JobStatus {
  @JsonValue('open')
  open,
  @JsonValue('closed')
  closed,
  @JsonValue('unknown')
  unknown,
}
```

- [ ] **Step 2: Add the mirror-comment to `application_status.dart`**

```dart
import 'package:json_annotation/json_annotation.dart';

part 'application_status.g.dart';

/// Mirrors backend `ApplicationStatus` (`core/src/jobify/db/models.py:670`, a
/// `StrEnum` with members `APPLIED="applied"`/`WITHDRAWN="withdrawn"`).
/// `unknown` is a client-only sentinel — DTO fields using this enum must
/// declare `@JsonKey(unknownEnumValue: ApplicationStatus.unknown)` (done today
/// in `ApplicationDto.status`). Round-trip pinned by
/// `test/unit/data/jobs/application_status_test.dart`.
@JsonEnum(alwaysCreate: true)
enum ApplicationStatus {
  @JsonValue('applied')
  applied,
  @JsonValue('withdrawn')
  withdrawn,
  @JsonValue('unknown')
  unknown,
}
```

- [ ] **Step 3: Write the failing test for `JobStatus` (via the real DTO that uses it)**

Create `app/test/unit/data/jobs/job_status_test.dart`:
```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/jobs/job_status.dart';

// Pins the backend JobStatus contract (core/src/jobify/db/models.py:404) via
// the real DTO that carries it. A backend enum rename/addition with no
// matching client update fails here, not as a silent unknownEnumValue
// fallback discovered in prod.
void main() {
  test('JobSummaryDto parses both real backend JobStatus values', () {
    final open = JobSummaryDto.fromJson(const {
      'id': 'j1',
      'title': 'Backend Engineer',
      'locations': ['Bengaluru'],
      'status': 'open',
      'posted_at': '2026-05-01T00:00:00Z',
    });
    expect(open.status, JobStatus.open);

    final closed = JobSummaryDto.fromJson(const {
      'id': 'j2',
      'title': 'Backend Engineer',
      'locations': ['Bengaluru'],
      'status': 'closed',
      'posted_at': '2026-05-01T00:00:00Z',
    });
    expect(closed.status, JobStatus.closed);
  });

  test('an unrecognised JobStatus value degrades to the unknown sentinel', () {
    final dto = JobSummaryDto.fromJson(const {
      'id': 'j3',
      'title': 'Backend Engineer',
      'locations': ['Bengaluru'],
      'status': 'archived',
      'posted_at': '2026-05-01T00:00:00Z',
    });
    expect(dto.status, JobStatus.unknown);
  });
}
```

- [ ] **Step 4: Run it to verify the two real-value cases already pass and would fail on drift**

Run: `cd app && flutter test test/unit/data/jobs/job_status_test.dart`
Expected: PASS (the DTO/enum already implement this correctly today — this test is a regression pin, not a bugfix).

- [ ] **Step 5: Write the fixture test for `ApplicationStatus`**

Create `app/test/unit/data/jobs/application_status_test.dart`:
```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/jobs/application_status.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';

// Pins the backend ApplicationStatus contract (core/src/jobify/db/models.py:670)
// via the real DTO that carries it — mirrors the job_status_test.dart pattern.
void main() {
  test('ApplicationDto parses both real backend ApplicationStatus values', () {
    final applied = ApplicationDto.fromJson(const {
      'id': 'app1',
      'job_id': 'j1',
      'status': 'applied',
      'source': 'feed',
      'created_at': '2026-05-01T00:00:00Z',
      'updated_at': '2026-05-01T00:00:00Z',
    });
    expect(applied.status, ApplicationStatus.applied);

    final withdrawn = ApplicationDto.fromJson(const {
      'id': 'app2',
      'job_id': 'j1',
      'status': 'withdrawn',
      'source': 'detail',
      'created_at': '2026-05-01T00:00:00Z',
      'updated_at': '2026-05-02T00:00:00Z',
    });
    expect(withdrawn.status, ApplicationStatus.withdrawn);
  });

  test('an unrecognised ApplicationStatus value degrades to the unknown sentinel', () {
    final dto = ApplicationDto.fromJson(const {
      'id': 'app3',
      'job_id': 'j1',
      'status': 'expired',
      'source': 'feed',
      'created_at': '2026-05-01T00:00:00Z',
      'updated_at': '2026-05-01T00:00:00Z',
    });
    expect(dto.status, ApplicationStatus.unknown);
  });
}
```

- [ ] **Step 6: Run both new tests + the full suite to verify no regression**

Run: `cd app && flutter test test/unit/data/jobs/`
Expected: PASS, 6 tests (3 groups × the two files, some tests have 2 expects).

Run: `cd app && dart format --set-exit-if-changed lib test && flutter analyze && flutter test`
Expected: all PASS/clean.

- [ ] **Step 7: Commit**

```bash
git add app/lib/data/jobs/job_status.dart app/lib/data/jobs/application_status.dart app/test/unit/data/jobs/job_status_test.dart app/test/unit/data/jobs/application_status_test.dart
git commit -m "test(app): pin JobStatus/ApplicationStatus to the backend contract, MeDto-style (arch review #9)"
```

---

### Task 7: Wire a real trigger for `sweep_notifications` (finding #10, roadmap #7)

**Decision (confirmed with user):** wire a Celery beat schedule rather than descoping.

**Files:**
- Modify: `core/src/jobify/settings.py` (add `notify_sweep_interval_seconds`)
- Modify: `core/src/jobify/celery_app.py` (add `beat_schedule`)
- Modify: `worker/README.md` (Beat section — no longer "INERT today")
- Test: `tests/unit/test_celery_app.py` (new)

**Interfaces:**
- Consumes: existing `Settings` class (`core/src/jobify/settings.py`) — same `Field(default=..., ge=..., le=..., alias="JOBIFY_...")` pattern as `notify_batch_size` (line 167).
- Produces: `settings.notify_sweep_interval_seconds: int`; `celery_app.conf.beat_schedule["sweep-notifications"]` entry with `"task": "jobify.sweep_notifications"`.

- [ ] **Step 1: Add the interval setting**

In `core/src/jobify/settings.py`, immediately after the existing `notify_batch_size` field (around line 167-172), add:
```python
    notify_sweep_interval_seconds: int = Field(
        default=60,
        ge=5,
        le=3600,
        alias="JOBIFY_NOTIFY_SWEEP_INTERVAL_SECONDS",
        description="How often Celery beat dispatches sweep_notifications.",
    )
```

- [ ] **Step 2: Write the failing test**

Create `tests/unit/test_celery_app.py`:
```python
"""sweep_notifications must actually be scheduled — see arch review finding #10:
routes write Notification rows but nothing was dispatching the sweeper."""

from __future__ import annotations

from jobify.celery_app import celery_app


def test_sweep_notifications_is_beat_scheduled() -> None:
    schedule = celery_app.conf.beat_schedule
    assert "sweep-notifications" in schedule
    entry = schedule["sweep-notifications"]
    assert entry["task"] == "jobify.sweep_notifications"
    assert entry["schedule"] > 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_celery_app.py -v`
Expected: FAIL — `KeyError: 'sweep-notifications'` (no `beat_schedule` configured yet).

- [ ] **Step 4: Add the beat schedule**

In `core/src/jobify/celery_app.py`, add the import and the schedule entry:
```python
from celery import Celery
```
becomes:
```python
from celery import Celery
from celery.schedules import schedule as celery_schedule
```

And after the existing `celery_app.conf.update(...)` block (which sets `task_routes` etc.), add:
```python
celery_app.conf.beat_schedule = {
    "sweep-notifications": {
        "task": "jobify.sweep_notifications",
        "schedule": celery_schedule(run_every=settings.notify_sweep_interval_seconds),
    },
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_celery_app.py -v`
Expected: PASS.

- [ ] **Step 6: Update `worker/README.md`'s Beat section**

Replace:
```
## Beat (scheduler) — INERT today

No periodic tasks are scheduled yet (no beat_schedule). When one is added:

    uv run --env-file=.env celery -A jobify_worker.worker_app beat --loglevel=info
```
with:
```
## Beat (scheduler)

`sweep_notifications` runs every `JOBIFY_NOTIFY_SWEEP_INTERVAL_SECONDS` seconds
(default 60) via `celery_app.conf.beat_schedule`. Beat must run as its own
process alongside the worker — it only enqueues, it doesn't execute:

    uv run --env-file=.env celery -A jobify_worker.worker_app beat --loglevel=info
```

- [ ] **Step 7: Run the full backend CI verbatim**

Run: `uv run ruff check core/src api/src worker/src tests && uv run ruff format --check core/src api/src worker/src tests && uv run mypy && uv run pytest -v -m "not integration and not eval"`
Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add core/src/jobify/settings.py core/src/jobify/celery_app.py worker/README.md tests/unit/test_celery_app.py
git commit -m "feat(worker): schedule sweep_notifications via Celery beat (arch review #10)"
```

---

### Task 8: Consolidate `score_applicant`/`score_job`'s shared compute+UPSERT shape (finding #6, roadmap #8)

**Files:**
- Create: `worker/src/jobify_worker/tasks/_scoring_common.py`
- Modify: `worker/src/jobify_worker/tasks/score_applicant.py`
- Modify: `worker/src/jobify_worker/tasks/score_job.py`

**Interfaces:**
- Produces (from `_scoring_common.py`, consumed by both task modules):
  - `EXPLAIN_CONCURRENCY: int = 10`
  - `@dataclass(frozen=True, slots=True) class ScoringInput` — fields: `applicant_id: UUID`, `job_id: UUID`, `applicant_embedding: list[float]`, `applicant_embedding_model: str`, `applicant_locations: list[str]`, `applicant_years: Any`, `applicant_expected_ctc: Any`, `job_embedding: list[float]`, `job_embedding_model: str`, `job_title: str`, `job_locations: list[str]`, `job_min_exp_years: Any`, `job_max_exp_years: Any`, `job_ctc_min: Any`, `job_ctc_max: Any`, `employer_name: str`.
  - `@dataclass(frozen=True, slots=True) class ScoredMatch` — fields: `applicant_id: UUID`, `job_id: UUID`, `score: MatchScore`, `model_versions: dict[str, Any]`, `explanation: dict[str, str]`.
  - `async def explain_scores(explainer: MatchExplainer, inputs: list[ScoringInput], *, vector_weight: float, threshold: float) -> list[ScoredMatch]`
  - `def match_upsert_statement(scored: ScoredMatch) -> Any` (a SQLAlchemy `Insert` statement).

- [ ] **Step 1: Run the existing tests first to capture the pre-refactor baseline**

Run: `uv run pytest -v -m integration -k "score_applicant_worker or score_job_worker"`
Expected: PASS (baseline — these must still pass identically after Steps 2-4).

- [ ] **Step 2: Create the shared module**

Create `worker/src/jobify_worker/tasks/_scoring_common.py`:
```python
"""Shared compute + UPSERT logic for score_applicant/score_job.

score_applicant paginates jobs for one fixed applicant; score_job paginates
applicants for one fixed job. Once each task has resolved its batch of
(applicant, job) scoring inputs, the compute -> explain -> UPSERT steps are
identical (both tasks used to hand-copy this) — this module is the one copy.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import func

from jobify.db.models import Match
from jobify.scoring.explainer import ExplainContext
from jobify.scoring.match import MatchScore, score_match

if TYPE_CHECKING:
    from jobify.scoring.explainer import MatchExplainer

# Upper bound on concurrent explain() calls per batch (LLM impl hits Gemini).
EXPLAIN_CONCURRENCY = 10


@dataclass(frozen=True, slots=True)
class ScoringInput:
    """One (applicant, job) pair's scalars needed to compute + explain a match."""

    applicant_id: UUID
    job_id: UUID
    applicant_embedding: list[float]
    applicant_embedding_model: str
    applicant_locations: list[str]
    applicant_years: Any
    applicant_expected_ctc: Any
    job_embedding: list[float]
    job_embedding_model: str
    job_title: str
    job_locations: list[str]
    job_min_exp_years: Any
    job_max_exp_years: Any
    job_ctc_min: Any
    job_ctc_max: Any
    employer_name: str


@dataclass(frozen=True, slots=True)
class ScoredMatch:
    """One computed + explained match, ready for the UPSERT."""

    applicant_id: UUID
    job_id: UUID
    score: MatchScore
    model_versions: dict[str, Any]
    explanation: dict[str, str]


def _compute(
    inp: ScoringInput, *, vector_weight: float, threshold: float
) -> tuple[MatchScore, ExplainContext]:
    """Pure (no I/O) match score + explain context for one pair."""
    ms = score_match(
        applicant_embedding=inp.applicant_embedding,
        job_embedding=inp.job_embedding,
        applicant_locations=inp.applicant_locations,
        applicant_years=inp.applicant_years,
        applicant_expected_ctc=inp.applicant_expected_ctc,
        job_locations=inp.job_locations,
        job_min_exp_years=inp.job_min_exp_years,
        job_max_exp_years=inp.job_max_exp_years,
        job_ctc_min=inp.job_ctc_min,
        job_ctc_max=inp.job_ctc_max,
        vector_weight=vector_weight,
        threshold=threshold,
    )
    ctx = ExplainContext(
        components=ms.components,
        vector=ms.vector,
        structured=ms.structured,
        total=ms.total,
        threshold=threshold,
        job_title=inp.job_title,
        job_locations=inp.job_locations,
        job_min_exp_years=inp.job_min_exp_years,
        job_max_exp_years=inp.job_max_exp_years,
        job_ctc_max=inp.job_ctc_max,
        employer_name=inp.employer_name,
        applicant_expected_ctc=inp.applicant_expected_ctc,
        applicant_locations=inp.applicant_locations,
    )
    return ms, ctx


async def explain_scores(
    explainer: MatchExplainer,
    inputs: list[ScoringInput],
    *,
    vector_weight: float,
    threshold: float,
) -> list[ScoredMatch]:
    """Compute + explain a batch, bounded so a large batch doesn't stampede the LLM API."""
    pending = [
        (inp, *_compute(inp, vector_weight=vector_weight, threshold=threshold))
        for inp in inputs
    ]
    sem = asyncio.Semaphore(EXPLAIN_CONCURRENCY)

    async def _explain_bounded(ctx: ExplainContext) -> dict[str, str]:
        async with sem:
            return await explainer.explain(ctx)

    explanations = await asyncio.gather(*(_explain_bounded(ctx) for _, _, ctx in pending))
    return [
        ScoredMatch(
            applicant_id=inp.applicant_id,
            job_id=inp.job_id,
            score=ms,
            model_versions={
                "applicant_model": inp.applicant_embedding_model,
                "job_model": inp.job_embedding_model,
                "vector_weight": vector_weight,
                "threshold": threshold,
            },
            explanation=explanation,
        )
        for (inp, ms, _ctx), explanation in zip(pending, explanations, strict=True)
    ]


def match_upsert_statement(scored: ScoredMatch) -> Any:
    """The UPSERT both scoring tasks run per matched pair — same conflict target,
    same coalesce-guarded ``surfaced_at`` (never unset once set, see worker/CLAUDE.md
    -> Scoring worker)."""
    ms = scored.score
    return (
        pg_insert(Match)
        .values(
            applicant_id=scored.applicant_id,
            job_id=scored.job_id,
            vector_score=ms.vector,
            structured_score=ms.structured,
            total_score=ms.total,
            score_components=ms.components,
            model_versions=scored.model_versions,
            surfaced_at=func.now() if ms.crosses_threshold else None,
            explanation=scored.explanation,
        )
        .on_conflict_do_update(
            index_elements=["applicant_id", "job_id"],
            index_where=sa.text("deleted_at IS NULL"),
            set_={
                "vector_score": ms.vector,
                "structured_score": ms.structured,
                "total_score": ms.total,
                "score_components": ms.components,
                "model_versions": scored.model_versions,
                "surfaced_at": func.coalesce(
                    Match.surfaced_at,
                    sa.case(
                        (sa.literal(ms.crosses_threshold), func.now()),
                        else_=None,
                    ),
                ),
                "explanation": scored.explanation,
                "updated_at": func.now(),
            },
        )
    )
```

- [ ] **Step 3: Rewrite `score_applicant.py`'s compute/explain/UPSERT sections to call the shared module**

Replace the imports block (drop `sa`, `and_`, `pg_insert`, `func` — no longer needed directly; keep `select`):
```python
import sqlalchemy as sa
import structlog
from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import func

from jobify.celery_app import celery_app
from jobify.celery_app import settings as _settings
from jobify.db.models import (
    Applicant,
    ApplicantEmbedding,
    ApplicantPreferences,
    Employer,
    Job,
    JobEmbedding,
    JobStatus,
    Match,
)
from jobify.scoring.match import TransientScoringError, score_match
from jobify_worker.runtime import get_session_maker
```
with:
```python
import structlog
from sqlalchemy import and_, select

from jobify.celery_app import celery_app
from jobify.celery_app import settings as _settings
from jobify.db.models import (
    Applicant,
    ApplicantEmbedding,
    ApplicantPreferences,
    Employer,
    Job,
    JobEmbedding,
    JobStatus,
)
from jobify.scoring.match import TransientScoringError
from jobify_worker.runtime import get_session_maker
from jobify_worker.tasks._scoring_common import ScoringInput, explain_scores, match_upsert_statement
```

Remove the module-level `_EXPLAIN_CONCURRENCY = 10` constant (now lives in `_scoring_common`).

Replace the "(no DB) compute" section through the end of the "Txn 2: UPSERT" section:
```python
    # --- (no DB) compute ---
    from jobify.scoring.explainer import ExplainContext
    from jobify_worker.runtime import get_match_explainer

    _explainer = get_match_explainer()

    pending: list[tuple[UUID, Any, str, ExplainContext]] = []
    for (
        job_id,
        job_title,
        job_locs,
        job_min_exp,
        job_max_exp,
        job_ctc_min,
        job_ctc_max,
        job_emb_vec,
        job_emb_model,
        employer_name,
    ) in scored_inputs:
        ms = score_match(
            applicant_embedding=applicant_emb_vec,
            job_embedding=job_emb_vec,
            applicant_locations=applicant_locs,
            applicant_years=applicant_years,
            applicant_expected_ctc=applicant_ctc,
            job_locations=job_locs,
            job_min_exp_years=job_min_exp,
            job_max_exp_years=job_max_exp,
            job_ctc_min=job_ctc_min,
            job_ctc_max=job_ctc_max,
            vector_weight=_settings.match_vector_weight,
            threshold=_settings.match_surface_threshold,
        )
        ctx = ExplainContext(
            components=ms.components,
            vector=ms.vector,
            structured=ms.structured,
            total=ms.total,
            threshold=_settings.match_surface_threshold,
            job_title=job_title,
            job_locations=job_locs,
            job_min_exp_years=job_min_exp,
            job_max_exp_years=job_max_exp,
            job_ctc_max=job_ctc_max,
            employer_name=employer_name,
            applicant_expected_ctc=applicant_ctc,
            applicant_locations=applicant_locs,
        )
        pending.append((job_id, ms, job_emb_model, ctx))

    # explain() never raises (explainer contract) and the LLM impl is
    # I/O-bound — run the batch concurrently instead of one Gemini round-trip
    # per job, bounded so a large batch doesn't stampede the API.
    sem = asyncio.Semaphore(_EXPLAIN_CONCURRENCY)

    async def _explain_bounded(ctx: ExplainContext) -> dict[str, str]:
        async with sem:
            return await _explainer.explain(ctx)

    explanations = await asyncio.gather(*(_explain_bounded(ctx) for *_, ctx in pending))
    scores: list[tuple[UUID, Any, str, dict[str, str]]] = [
        (job_id, ms, model, explanation)
        for (job_id, ms, model, _ctx), explanation in zip(pending, explanations, strict=True)
    ]

    # --- Txn 2: UPSERT each row ---
    async with sm() as session:
        try:
            for job_id, ms, job_emb_model, explanation in scores:
                model_versions = {
                    "applicant_model": applicant_emb_model,
                    "job_model": job_emb_model,
                    "vector_weight": _settings.match_vector_weight,
                    "threshold": _settings.match_surface_threshold,
                }
                stmt = (
                    pg_insert(Match)
                    .values(
                        applicant_id=applicant_id,
                        job_id=job_id,
                        vector_score=ms.vector,
                        structured_score=ms.structured,
                        total_score=ms.total,
                        score_components=ms.components,
                        model_versions=model_versions,
                        surfaced_at=func.now() if ms.crosses_threshold else None,
                        explanation=explanation,
                    )
                    .on_conflict_do_update(
                        index_elements=["applicant_id", "job_id"],
                        index_where=sa.text("deleted_at IS NULL"),
                        set_={
                            "vector_score": ms.vector,
                            "structured_score": ms.structured,
                            "total_score": ms.total,
                            "score_components": ms.components,
                            "model_versions": model_versions,
                            "surfaced_at": func.coalesce(
                                Match.surfaced_at,
                                sa.case(
                                    (sa.literal(ms.crosses_threshold), func.now()),
                                    else_=None,
                                ),
                            ),
                            "explanation": explanation,
                            "updated_at": func.now(),
                        },
                    )
                )
                await session.execute(stmt)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            _log.exception("score.upsert-failed", applicant_id=str(applicant_id))
            raise TransientScoringError(f"upsert failed: {type(exc).__name__}") from exc
```
with:
```python
    # --- (no DB) compute + explain ---
    from jobify_worker.runtime import get_match_explainer

    scoring_inputs = [
        ScoringInput(
            applicant_id=applicant_id,
            job_id=job_id,
            applicant_embedding=applicant_emb_vec,
            applicant_embedding_model=applicant_emb_model,
            applicant_locations=applicant_locs,
            applicant_years=applicant_years,
            applicant_expected_ctc=applicant_ctc,
            job_embedding=job_emb_vec,
            job_embedding_model=job_emb_model,
            job_title=job_title,
            job_locations=job_locs,
            job_min_exp_years=job_min_exp,
            job_max_exp_years=job_max_exp,
            job_ctc_min=job_ctc_min,
            job_ctc_max=job_ctc_max,
            employer_name=employer_name,
        )
        for (
            job_id,
            job_title,
            job_locs,
            job_min_exp,
            job_max_exp,
            job_ctc_min,
            job_ctc_max,
            job_emb_vec,
            job_emb_model,
            employer_name,
        ) in scored_inputs
    ]
    scores = await explain_scores(
        get_match_explainer(),
        scoring_inputs,
        vector_weight=_settings.match_vector_weight,
        threshold=_settings.match_surface_threshold,
    )

    # --- Txn 2: UPSERT each row ---
    async with sm() as session:
        try:
            for scored in scores:
                await session.execute(match_upsert_statement(scored))
            await session.commit()
        except Exception as exc:
            await session.rollback()
            _log.exception("score.upsert-failed", applicant_id=str(applicant_id))
            raise TransientScoringError(f"upsert failed: {type(exc).__name__}") from exc
```

Update the trailing log call, which referenced `len(scores)`:
```python
    _log.info(
        "score.applicant-complete",
        applicant_id=str(applicant_id),
        scored=len(scores),
        has_more=has_more,
    )
```
(unchanged — `scores` is still a list, `len()` still works.)

- [ ] **Step 4: Rewrite `score_job.py`'s compute/explain/UPSERT sections symmetrically**

Apply the exact same shape as Step 3, swapping the pagination variable (`applicant_id` varies per-row instead of `job_id`). Imports become:
```python
import structlog
from sqlalchemy import and_, select

from jobify.celery_app import celery_app
from jobify.celery_app import settings as _settings
from jobify.db.models import (
    Applicant,
    ApplicantEmbedding,
    ApplicantPreferences,
    Employer,
    Job,
    JobEmbedding,
    JobStatus,
)
from jobify.scoring.match import TransientScoringError
from jobify_worker.runtime import get_session_maker
from jobify_worker.tasks._scoring_common import ScoringInput, explain_scores, match_upsert_statement
```

Remove the module-level `_EXPLAIN_CONCURRENCY = 10` constant.

Replace the "(no DB) compute" through "Txn 2: UPSERT" sections with:
```python
    # --- (no DB) compute + explain ---
    from jobify_worker.runtime import get_match_explainer

    scoring_inputs = [
        ScoringInput(
            applicant_id=applicant_id,
            job_id=job_id,
            applicant_embedding=applicant_emb_vec,
            applicant_embedding_model=applicant_emb_model,
            applicant_locations=applicant_locs,
            applicant_years=applicant_years,
            applicant_expected_ctc=applicant_ctc,
            job_embedding=job_emb_vec,
            job_embedding_model=job_emb_model,
            job_title=job_title,
            job_locations=job_locs,
            job_min_exp_years=job_min_exp,
            job_max_exp_years=job_max_exp,
            job_ctc_min=job_ctc_min,
            job_ctc_max=job_ctc_max,
            employer_name=job_employer_name,
        )
        for (
            applicant_id,
            applicant_locs,
            applicant_years,
            applicant_ctc,
            applicant_emb_vec,
            applicant_emb_model,
        ) in scored_inputs
    ]
    scores = await explain_scores(
        get_match_explainer(),
        scoring_inputs,
        vector_weight=_settings.match_vector_weight,
        threshold=_settings.match_surface_threshold,
    )

    # --- Txn 2: UPSERT each row ---
    async with sm() as session:
        try:
            for scored in scores:
                await session.execute(match_upsert_statement(scored))
            await session.commit()
        except Exception as exc:
            await session.rollback()
            _log.exception("score.upsert-failed", job_id=str(job_id))
            raise TransientScoringError(f"upsert failed: {type(exc).__name__}") from exc
```

The trailing log line (`_log.info("score.job-complete", job_id=str(job_id), scored=len(scores), has_more=has_more)`) is unchanged.

- [ ] **Step 5: Run both worker test files to verify no regression**

Run: `uv run pytest -v -m integration -k "score_applicant_worker or score_job_worker"`
Expected: PASS — identical results to Step 1's baseline (same test count, same outcomes). Any new FAIL means the refactor changed observable behavior — diff the failing test's assertion against `_scoring_common.py` before proceeding.

- [ ] **Step 6: Run full backend CI verbatim**

Run: `uv run ruff check core/src api/src worker/src tests && uv run ruff format --check core/src api/src worker/src tests && uv run mypy && uv run pytest -v -m "not integration and not eval" && uv run pytest -v -m integration`
Expected: all green.

- [ ] **Step 7: Update `worker/CLAUDE.md`'s Scoring worker section to point at the new shared module**

Replace:
```
- **Two workers, one `score` queue:** `score_applicant` (from `embed_applicant` Txn3) + `score_job` (from `embed_job` Txn3), post-commit, broad-except. Pure-Python cosine (`jobify.scoring.vector`). Explanations run via bounded `asyncio.gather` (`_EXPLAIN_CONCURRENCY=10`), not per-item awaits (the explainer itself lives in `core/` — see `core/CLAUDE.md` → Match explanations).
```
with:
```
- **Two workers, one `score` queue:** `score_applicant` (from `embed_applicant` Txn3) + `score_job` (from `embed_job` Txn3), post-commit, broad-except. Each resolves its own batch (jobs-for-an-applicant vs applicants-for-a-job), then both hand off to the shared `tasks/_scoring_common.py` (`ScoringInput` → `explain_scores` → `match_upsert_statement`) for the compute/explain/UPSERT shape — don't hand-copy that logic back into either task. Pure-Python cosine (`jobify.scoring.vector`). Explanations run via bounded `asyncio.gather` (`EXPLAIN_CONCURRENCY=10` in `_scoring_common.py`), not per-item awaits (the explainer itself lives in `core/` — see `core/CLAUDE.md` → Match explanations).
```

- [ ] **Step 8: Commit**

```bash
git add worker/src/jobify_worker/tasks/_scoring_common.py worker/src/jobify_worker/tasks/score_applicant.py worker/src/jobify_worker/tasks/score_job.py worker/CLAUDE.md
git commit -m "refactor(worker): extract shared compute/explain/UPSERT logic from score_applicant+score_job (arch review #6)"
```

---

## Final verification (after all 8 tasks)

- [ ] Run the full backend CI verbatim from repo root:
  `uv run ruff check core/src api/src worker/src tests && uv run ruff format --check core/src api/src worker/src tests && uv run mypy && uv run pytest -v -m "not integration and not eval" && uv run pytest -v -s -m eval && uv run pytest -v -m integration`
- [ ] Run the app CI verbatim from `app/`:
  `dart format --set-exit-if-changed lib test && flutter analyze && flutter test`
- [ ] Run the frontend CI verbatim from `frontend/`:
  `npm run build`
- [ ] Confirm every task's commit is present: `git log --oneline -9`
