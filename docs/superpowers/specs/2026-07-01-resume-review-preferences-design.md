# Resume review + job preferences capture — design

Date: 2026-07-01

## Problem

Today, uploading a resume (`POST /v1/applicants/me/resumes`) kicks off an async
parse and the app polls for status, but the user never sees what was
extracted, and nothing captures what kind of role, location, or expected CTC
they're looking for. Applicants who haven't uploaded a resume at all get no
active nudge beyond a line of empty-state text on the feed.

This feature adds:

1. A post-parse review step that shows the user a summary of their parsed
   resume and asks 3 questions: desired role, location, expected CTC.
2. A persistent nudge for applicants who haven't uploaded a resume yet, and a
   lighter nudge for applicants whose resume is in but the 3 answers aren't.

## Current state (context)

- `Resume` (`core/src/jobify/db/models.py`): `parse_status`
  (`PENDING`→`PARSING`→`PARSED`/`FAILED`), `parsed_json` (unstructured JSONB).
- `ParsedResume` (`core/src/jobify/integrations/parser/base.py`) extracts:
  name, email, phone, skills, experience, education, certifications. It does
  **not** extract desired role, desired location, or expected CTC — those
  are forward-looking preferences, not facts the parser can read off a resume.
- `Applicant` currently has `locations` (array) and `expected_ctc` (numeric),
  editable via `PATCH /v1/applicants/me`, which triggers an async rescore.
  There is no `desired_role`-shaped field anywhere in the schema today.
- `ResumeScreen` (`app/lib/presentation/resume/resume_screen.dart`) uploads,
  polls parse status at 2s/5s, and shows a status badge. No review step, no
  connection to profile fields.
- No profile-completion nudge pattern exists anywhere in the app today; the
  feed's empty state is static text.
- There are no real users on this platform yet — no backfill/migration
  concerns for existing data.

## Data model

New table, replacing `Applicant.locations` / `Applicant.expected_ctc` as the
single source for those two fields, and adding the new `desired_role`:

```python
class RoleCategory(StrEnum):
    SOFTWARE_ENGINEERING = "software_engineering"
    DATA_ANALYTICS = "data_analytics"
    PRODUCT_MANAGEMENT = "product_management"
    DESIGN = "design"
    SALES = "sales"
    MARKETING = "marketing"
    CUSTOMER_SUPPORT = "customer_support"
    OPERATIONS = "operations"
    FINANCE_ACCOUNTING = "finance_accounting"
    HR_RECRUITING = "hr_recruiting"
    LEGAL = "legal"
    CONSULTING = "consulting"
    BUSINESS_DEVELOPMENT = "business_development"
    CONTENT_COMMUNICATIONS = "content_communications"
    ADMINISTRATION = "administration"
    OTHER = "other"


class ApplicantPreferences(Base):
    __tablename__ = "applicant_preferences"

    id: Mapped[UuidPK]
    applicant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobify.applicants.id", ondelete="CASCADE"),
        nullable=False,
    )
    desired_role: Mapped[RoleCategory | None] = mapped_column(
        # StrEnum at the boundary, plain varchar in the DB — same precedent as
        # consent scopes (a native PG enum makes adding a value a painful
        # autocommit migration; see core/CLAUDE.md).
        SAEnum(
            RoleCategory,
            name="role_category",
            native_enum=False,
            create_constraint=False,
            length=50,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    locations: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), nullable=False, server_default="{}"
    )
    expected_ctc: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    deleted_at: Mapped[DeletedAt]

    __table_args__ = (
        Index(
            "ix_applicant_preferences_applicant_live",
            "applicant_id",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
    )
```

One applicant → at most one live preferences row, enforced by a soft-delete-
aware partial unique index (same pattern as `Employer.name_norm`).

**Migration** (hand-written, `core/src/jobify/db/migrations/versions/`):
creates `applicant_preferences` (`desired_role` as plain varchar — the
16-value vocabulary is enforced at the API boundary by the `RoleCategory`
StrEnum, not a PG enum type) and drops `Applicant.locations` +
`Applicant.expected_ctc`. No backfill — there are no
existing users. `Applicant.current_ctc`, `years_experience`,
`notice_period_days`, `full_name` are untouched; they are not part of this
feature.

Any code that currently reads `Applicant.locations` / `Applicant.expected_ctc`
(scoring/embedding inputs in `worker/`, profile serialization in
`api/src/jobify_api/routes/applicants.py`, seed scripts) must be repointed at
`ApplicantPreferences` as part of this change — this is a consolidation, not
an addition, for those two fields.

## API

In `api/src/jobify_api/routes/applicants.py`, alongside the existing
`PATCH /v1/applicants/me`:

- `GET /v1/applicants/me/preferences` → `PreferencesRead`
  (`desired_role: RoleCategory | None`, `locations: list[str]`,
  `expected_ctc: Decimal | None` — serialized as a JSON *string*, like every
  other Decimal on the wire). The row always exists: it is eagerly created
  empty at signup by `AuthService._upsert_identity` (same pattern as consent
  seeding), which avoids a "row missing" vs "row with nulls" distinction on
  the frontend without a write-on-read GET.
- `PATCH /v1/applicants/me/preferences` → `PreferencesUpdate` (all fields
  optional — partial update, same shape as the existing profile PATCH).
  Changing `locations` or `expected_ctc` dispatches the same async rescore
  task the profile PATCH triggers today; the trigger condition for those two
  fields moves from "Applicant fields changed" to "Preferences fields
  changed." `PATCH /v1/applicants/me` still triggers rescore on
  `years_experience` changes as it does today — unaffected by this change,
  since that field stays on `Applicant`.

**Role options**: `RoleCategory` values are a plain shared enum — defined
once in the backend, mirrored as a matching Dart enum in the Flutter app. No
dedicated `/meta/role-categories` endpoint (same approach as `JobStatus`,
which has no meta endpoint either). This is intentionally capture-only for
this iteration — `desired_role` is not wired into matching/scoring.

**Resume summary**: `ResumeRead` (`api/src/jobify_api/routes/resumes.py:47`)
currently returns metadata only — `parsed_json` is NOT exposed today
(verified against the route source during planning; the original draft of
this section was wrong). Add `parsed_json: dict[str, Any] | None = None` to
`ResumeRead`; `from_attributes=True` picks it up off the existing
`Resume.parsed_json` column with no other backend change. The new screen
reads name/skills/experience/education from it directly.

## Frontend (Flutter)

**New screen**: `PreferencesScreen`
(`app/lib/presentation/preferences/preferences_screen.dart`) — a single form:

- Optional "Your resume" summary card at top (name, skills, experience,
  education from the resume's `parsed_json`). If the resume's parse failed,
  this card shows a fallback message ("we couldn't read your resume — tell
  us directly") instead of parsed fields.
- 3 fields: `RoleCategory` dropdown, location text input, expected CTC
  numeric input.
- Save button → `PATCH /v1/applicants/me/preferences`.
- Skip link → navigates back to feed without saving anything. There is no
  separate "dismissed" flag; skipping just means the fields stay empty, and
  the derived nudge (see below) will surface again next time the feed loads.

**Trigger points:**

1. **Post-upload.** `ResumeScreen`'s existing poll, on observing
   `parse_status` transition to `PARSED` or `FAILED`, checks
   `GET /me/preferences`; if any of the 3 fields are still empty, it
   navigates to `PreferencesScreen` with the resume's parsed data (or the
   failure fallback) pre-loaded.
2. **Nudge banner.** The feed/home screen adds a persistent banner above the
   feed (the static empty-state text stays), derived from two checks (resume
   exists? preferences complete?) with no additional stored state:
   - No resume at all → "Upload your resume so we can find you better
     roles" → taps into `ResumeScreen`.
   - Resume exists, preferences incomplete → "Tell us what you're looking
     for" → taps into `PreferencesScreen` (summary card shown if a parsed
     resume is available).
   - Both complete → no banner.
   The banner has no dismiss control — it's fully derived from resume/
   preferences state, so it simply stops rendering once the underlying data
   is complete.

**Profile edit screen** (`app/lib/presentation/profile/edit_profile_screen.dart`)
keeps its existing simple edit UI for location/CTC from the user's
perspective — it's just repointed at `GET`/`PATCH /me/preferences` under the
hood instead of the old `Applicant` fields. It does not route through
`PreferencesScreen`; that screen is only used at the two trigger points
above.

## Error handling

- Save fails on `PreferencesScreen` (network/5xx) → error `SnackBar`,
  input retained, retryable — same pattern as the existing profile-edit
  screen.
- Invalid `desired_role` value → 422 via Pydantic enum validation, surfaced
  as a field-level error.
- Parse `FAILED` → summary card fallback text; the 3-field form is fully
  usable regardless, since it does not depend on parse having succeeded.
- `GET /me/preferences` with no live row → defensive 500
  `applicant_preferences_missing` (unreachable in the real system — the row
  is eagerly created at signup; same shape as `require_applicant`'s
  `applicant_missing` 500).

## Testing

- Backend unit: `RoleCategory` enum round-trip; `ApplicantPreferences`
  model/migration.
- Backend integration (`tests/integration/`):
  `GET`/`PATCH /v1/applicants/me/preferences` — auth required, partial
  update semantics, eager-create-at-signup (asserted in
  `test_auth_signin.py`), rescore task dispatched on
  `locations`/`expected_ctc` change, 422 on invalid enum value. Mirrors the
  existing profile-PATCH tests in `test_applicants.py`.
- Frontend widget tests: `PreferencesScreen` renders the parsed summary
  (including the `FAILED`-parse fallback), form validation, Skip navigates
  away without saving; feed-banner logic for all 3 states (no resume /
  resume-but-incomplete-prefs / complete).
- The OpenAPI snapshot pin (see `jobify-arch-hardening-guards` in
  `core/CLAUDE.md`) will need regenerating — new routes/schemas are an
  expected, reviewable diff, not a regression.

## Explicitly out of scope

- Wiring `desired_role` (or the other two fields) into the matching/scoring
  pipeline — capture-only for this iteration.
- A dedicated role-taxonomy management endpoint or admin UI — the enum is a
  small, hardcoded, shared list.
- Redirecting profile-screen edits through the guided `PreferencesScreen` —
  profile screen keeps its own simple edit UI.
- Backfilling existing `Applicant.locations`/`expected_ctc` data — there are
  no existing users.
