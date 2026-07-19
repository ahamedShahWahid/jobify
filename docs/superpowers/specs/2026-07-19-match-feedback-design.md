# Match feedback capture + admin Match QA — design

**Date:** 2026-07-19 · **Status:** approved · **Roadmap:** slice 1 of
`docs/mvp-launch-roadmap.md`

## Why

The BRD's MVP acceptance criterion "match relevance ≥ 75 %" is unmeasurable
today — nothing captures whether an applicant thinks a surfaced match fits.
This slice adds thumbs up/down on matches (the measurement), makes thumbs-down
hide the job from that applicant's feed (the UX users expect from "not
interested"), and gives admins a Match QA view over the ratings. The metric
needs ~500 ratings before it is believable, so shipping capture early starts
the calendar clock.

Decisions locked with Ahamed 2026-07-19:

1. **Record + hide:** a thumbs-down is stored for the metric AND removes the
   job from the applicant's feed. No score/weight adjustment in this slice
   (spec §14 #7 stays open — that needs labeled-data volume we don't have).
2. **Placement:** thumbs on feed cards AND a rating row beside the match
   explanation in job detail.
3. **Admin scope:** relevance metric + a filterable rated-matches list. No
   score-breakdown workbench yet.

## Storage decision

**Chosen: a new `match_feedback` table** (approach A), not columns on
`matches` (approach B). Rationale: `matches` rows are UPSERTed on every
rescore by two structurally-duplicated tasks (`score_applicant` /
`score_job`); feedback columns there would have to be preserved by both
UPSERT blocks forever. A separate table keeps ratings untouched by rescoring,
gives clean DSR semantics (ratings are applicant-owned behavioral data →
export + hard delete, while `matches` stays export-only/anonymized), and
follows the repo's soft-delete + partial-unique-index pattern.

## Data model

New table `match_feedback` (hand-written migration, next revision number):

| column | type | notes |
|---|---|---|
| `id` | UUID PK | `UuidPK` annotated type |
| `applicant_id` | UUID FK → `applicants.id` | `ondelete=CASCADE` |
| `job_id` | UUID FK → `jobs.id` | `ondelete=CASCADE` |
| `rating` | varchar + CHECK `('up','down')` | migration-0021 precedent (varchar+CHECK, not native enum) |
| `created_at` / `updated_at` | timestamptz | repo-standard annotated types |
| `deleted_at` | timestamptz NULL | soft delete, like every domain table |

Indexes: partial unique `(applicant_id, job_id) WHERE deleted_at IS NULL`
(one live rating per pair; re-rating UPDATEs the row); partial index on
`(rating, created_at DESC) WHERE deleted_at IS NULL` for the admin list +
summary queries.

Keyed on `(applicant_id, job_id)` — the same stable identity `matches` uses —
not `match_id`, so a rating survives match-row UPSERTs untouched.

**DSR:** `match_feedback` joins `EXPECTED_PII_TABLES` — included in **both**
export and delete (applicant-owned behavioral data). The contract-pin test
(`tests/unit/dsr/test_dsr_coverage.py`) is updated in the same commit that
adds the table.

**Python model:** `MatchFeedback` in `core/src/jobify/db/models.py` with a
`MatchFeedbackRating` StrEnum (`UP`/`DOWN`).

## API

### Applicant endpoints (route file `routes/match_feedback.py`)

- `PUT /v1/jobs/{job_id}/match-feedback` body `{"rating": "up"|"down"}` →
  200 with the stored rating. Upsert: revives/updates a soft-deleted or
  existing row. **404** (uniform not-found shape) when the applicant has no
  *surfaced* match for that job — mirrors the `/jobs/{id}/save` precedent and
  avoids leaking job existence.
- `DELETE /v1/jobs/{job_id}/match-feedback` → 204, soft-deletes the rating
  (Undo). 404 if no live rating.
- Auth: applicant role, self-scoped (applicant resolved from the token —
  never from a param).

### Feed changes (`routes/feed.py`)

- Exclude thumbs-down jobs:
  `outerjoin(MatchFeedback, and_(applicant/job keys match, deleted_at IS NULL, rating == 'down'))`
  then `.where(MatchFeedback.id.is_(None))`. The soft-delete and rating
  predicates live **in the ON clause** (WHERE-clause form silently drops
  parent rows / breaks keyset pagination — the known outer-join trap).
- Feed items and the job-detail match payload gain a nullable
  `my_feedback: "up" | "down" | null` field so clients render current state.
  (Thumbs-down jobs vanish from the feed but stay reachable via saved jobs /
  applications, so job detail must still render the rating state.)

### Admin endpoints (route file `routes/admin/match_feedback.py`)

- `GET /v1/admin/match-feedback?rating=&cursor=&limit=` — keyset-paginated
  (reuse `routes/admin/_common.py`'s `{created_at, id}` cursor) list of rated
  matches: rating, timestamps, job (id/title/employer name), applicant
  (id/name), match `total_score`, and the match `explanation`. Soft-deleted
  ratings excluded.
- `GET /v1/admin/match-feedback/summary` — `{all_time: {up, down, share},
  last_30d: {up, down, share}}` where `share = up / (up + down)` (null when
  denominator is 0). This is the BRD "match relevance" number.
- Admin role required, same guard as the other admin routes.

OpenAPI snapshot (`tests/unit/openapi_snapshot.json`) regenerated in the same
change. No worker/outbox involvement — ratings are synchronous writes.

## Flutter app

- **Feed card** (`presentation/feed/feed_item_card.dart`): thumb-up /
  thumb-down icon pair. Down → optimistic removal from the list + snackbar
  "Hidden from your feed" with an **Undo** action (calls DELETE, re-inserts).
  Up → filled state toggle.
- **Job detail** (`presentation/job_detail/`): a rating row beside the match
  explanation ("Was this match right for you?"). Same controls, no hide
  behavior (detail stays open), snackbar confirms.
- **Controllers:** one small controller per action following the
  `save_job_controller.dart` pattern (`rate_match_controller`,
  `clear_match_feedback_controller`), invalidating the feed + job-detail
  providers on success.
- **DTOs:** `my_feedback` added to the feed/match DTOs with a
  `MatchFeedbackRating` wire enum carrying `@JsonKey(unknownEnumValue:
  unknown)`; the `unknown` sentinel never serializes (omit the key). Pinned
  with the `MeDto`-style mirror comment + literal-JSON round-trip fixture
  test, including the enum wire map round-trip.

## Console (frontend)

New admin page **Match QA** (`sites/console/pages/admin/MatchQA.tsx`), nav
entry beside Analytics:

- Summary header: all-time share %, 30-day share %, up/down counts, and a
  caption when total rated < 500: "below n=500 — not yet statistically
  believable".
- Table of rated matches (columns per the admin list endpoint) with a
  rating filter (all/up/down) and cursor "load more", following the existing
  console list-page pattern. Percentages/dates go through
  `shared/format.ts` (IST display).
- `sites/console/api/types.ts` extended with the two response shapes,
  header comment citing the real backend files.

## Error handling

- Rating a job with no surfaced match → uniform 404 (no job-existence leak).
- Double-submit / re-rate → idempotent upsert, last write wins.
- Feed exclusion degrades safely: a soft-deleted `down` row must NOT hide the
  job (pinned by test — both degrade paths: missing row and soft-deleted row).
- Client failures: optimistic card removal rolls back on API error (snackbar
  with retry); controllers surface `AsyncValue.error`, never bare
  `.value == null` branching.

## Testing

- **Unit:** feedback service (upsert/revive/clear), feed exclusion incl. both
  outer-join degrade paths, DSR coverage pin update, soft-delete invariant
  auto-covers the new model, summary math (zero-denominator).
- **Integration:** PUT/DELETE lifecycle + 404s + role guards; feed hides on
  down, restores on undo; admin list pagination + filter; admin summary;
  DSR export/delete round-trip includes `match_feedback`.
- **Flutter:** widget tests for card thumbs (optimistic removal + undo) and
  detail rating row; DTO fixture round-trip incl. enum wire map.
- **Frontend:** `npm run build` CI gate (existing); no new test
  infrastructure.
- CI verbatim commands per root `CLAUDE.md` before claiming green.

## Out of scope

- Feedback influencing scoring/ranking weights (spec §14 #7 — needs data).
- Score-breakdown QA workbench, re-score actions.
- Recruiter-side feedback, free-text reasons, notification of changes.
