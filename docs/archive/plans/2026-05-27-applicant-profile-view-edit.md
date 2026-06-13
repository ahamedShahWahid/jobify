# Applicant Profile View + Edit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an applicant view and edit their profile (`full_name`, `locations`, `notice_period_days`, `current_ctc`, `expected_ctc`, `years_experience`) via a new `PATCH /v1/applicants/me` endpoint and a Flutter Edit Profile screen, re-triggering matching when relevant fields change.

**Architecture:** New FastAPI route module `routes/applicants.py` (PATCH, reusing the resumes error-ladder + reusing `me.py`'s `MeResponse`); fire-and-forget `score_applicant` dispatch post-commit. Flutter: extend `MeRepository` with `updateProfile`, a new request DTO, a `ProfileEditController`, a read-only details section on the Profile screen, and a new `EditProfileScreen` at `/profile/edit`.

**Tech Stack:** FastAPI + Pydantic v2 + async SQLAlchemy + Celery; Flutter + Riverpod 4 codegen + dio + go_router + json_serializable + intl.

Spec: `docs/superpowers/specs/2026-05-27-applicant-profile-view-edit-design.md`

---

## File Structure

**Backend (`api/`):**
- Create: `src/kpa/routes/applicants.py` — `ProfileUpdate` model + `PATCH /v1/applicants/me` handler + `_require_applicant` (copied) + `_dispatch_score`.
- Modify: `src/kpa/app_factory.py` — register the new router.
- Create: `tests/integration/test_profile_update.py`.

**App (`app/`):**
- Create: `lib/data/me/profile_update_dto.dart` (+ generated `.g.dart`).
- Modify: `lib/data/me/me_repository.dart`, `lib/data/me/me_api.dart`, `lib/data/me/me_repository_impl.dart`.
- Create: `lib/presentation/profile/profile_edit_controller.dart` (+ `.g.dart`).
- Create: `lib/presentation/profile/ctc_format.dart`.
- Create: `lib/presentation/profile/edit_profile_screen.dart`.
- Modify: `lib/presentation/profile/profile_screen.dart`, `lib/presentation/routing/router.dart`, `lib/presentation/routing/routes.dart`.
- Modify (fakes): `test/helpers/fake_repositories.dart`, `test/widget/profile_screen_test.dart`.
- Create tests: `test/unit/presentation/profile/profile_edit_controller_test.dart`, `test/widget/edit_profile_screen_test.dart`; extend `test/unit/data/me/me_repository_impl_test.dart`.

---

## Task 1: Backend — PATCH endpoint (happy-path partial update)

**Files:**
- Create: `api/src/kpa/routes/applicants.py`
- Modify: `api/src/kpa/app_factory.py:75` (add include_router)
- Test: `api/tests/integration/test_profile_update.py`

All commands run from `api/`.

- [ ] **Step 1: Write the failing test**

Create `api/tests/integration/test_profile_update.py`:

```python
"""Integration tests for PATCH /v1/applicants/me."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from kpa.auth.google_verifier import GoogleClaims
from kpa.db.models import Applicant

pytestmark = pytest.mark.integration


def _claims() -> GoogleClaims:
    return GoogleClaims(
        sub="google-sub-profile",
        iss="https://accounts.google.com",
        aud="test.apps.googleusercontent.com",
        email="alice@example.com",
        email_verified=True,
        name="Alice",
    )


async def _signin(client: httpx.AsyncClient, google_verifier) -> dict:
    google_verifier.canned["tok"] = _claims()
    resp = await client.post("/v1/auth/oauth/google", json={"id_token": "tok"})
    assert resp.status_code == 200
    return resp.json()


async def test_patch_partial_update(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    signin = await _signin(async_client, google_verifier)
    access = signin["access_token"]

    resp = await async_client.patch(
        "/v1/applicants/me",
        headers={"Authorization": f"Bearer {access}"},
        json={"locations": ["Pune", "Bengaluru"], "expected_ctc": 1800000},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["applicant"]["locations"] == ["Pune", "Bengaluru"]
    assert body["applicant"]["expected_ctc"] == "1800000.00"
    # full_name untouched (still the Google name).
    assert body["applicant"]["full_name"] == "Alice"

    row = (
        await session.execute(
            select(Applicant).where(Applicant.user_id == signin["user"]["id"])
        )
    ).scalar_one()
    assert row.locations == ["Pune", "Bengaluru"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest -v -m integration tests/integration/test_profile_update.py::test_patch_partial_update`
Expected: FAIL — 404/405 (route not registered).

- [ ] **Step 3: Create the route module**

Create `api/src/kpa/routes/applicants.py`:

```python
"""Applicant profile update — PATCH /v1/applicants/me.

The authenticated applicant edits their own profile fields. A change to a
matching-relevant field (locations / expected_ctc / years_experience) fires a
fire-and-forget rescore post-commit, because those feed the structured score
(the embedding is built from the resume, not these fields).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.dependencies import current_user
from kpa.db.models import Applicant, User, UserRole
from kpa.db.session import get_session
from kpa.routes.me import ApplicantRead, MeResponse

_log = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/applicants/me", tags=["applicants"])

# Fields whose change must trigger a rescore (they drive the structured score).
_MATCHING_FIELDS = {"locations", "expected_ctc", "years_experience"}


class ProfileUpdate(BaseModel):
    """Partial profile update. Only keys present in the request are applied
    (`model_fields_set`); an explicit null clears a nullable column. `full_name`
    and `locations` are non-nullable and reject an explicit null."""

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    locations: (
        list[Annotated[str, Field(min_length=1, max_length=100)]] | None
    ) = Field(default=None, max_length=10)
    notice_period_days: int | None = Field(default=None, ge=0, le=365)
    current_ctc: Decimal | None = Field(
        default=None, ge=0, le=Decimal("9999999999.99")
    )
    expected_ctc: Decimal | None = Field(
        default=None, ge=0, le=Decimal("9999999999.99")
    )
    years_experience: Decimal | None = Field(default=None, ge=0, le=Decimal("60"))

    @model_validator(mode="after")
    def _no_null_for_required(self) -> "ProfileUpdate":
        for f in ("full_name", "locations"):
            if f in self.model_fields_set and getattr(self, f) is None:
                raise ValueError(f"{f} cannot be null")
        return self


async def _require_applicant(user: User, session: AsyncSession) -> Applicant:
    """Resolve the authenticated user to a live applicants row.

    403 not_an_applicant if role != APPLICANT; 500 applicant_missing if the
    paired row is absent (sign-in provisions it — defense in depth).
    """
    if user.role != UserRole.APPLICANT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="not_an_applicant"
        )
    applicant = (
        await session.execute(
            select(Applicant).where(
                Applicant.user_id == user.id,
                Applicant.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if applicant is None:
        _log.error("applicant.row-missing-for-applicant-role", user_id=str(user.id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="applicant_missing",
        )
    return applicant


def _dispatch_score(applicant_id: UUID) -> None:
    """Fire score_applicant.delay(...) post-commit, fire-and-forget. A broker
    outage MUST NOT fail the save — same pattern as embed.py:_dispatch_score."""
    from kpa.workers.tasks.score_applicant import score_applicant

    try:
        score_applicant.delay(str(applicant_id))
    except Exception:
        _log.warning(
            "score.dispatch-failed", applicant_id=str(applicant_id), exc_info=True
        )


@router.patch("", response_model=MeResponse, status_code=status.HTTP_200_OK)
async def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MeResponse:
    applicant = await _require_applicant(user, session)

    changed_matching = False
    for name in payload.model_fields_set:
        setattr(applicant, name, getattr(payload, name))
        if name in _MATCHING_FIELDS:
            changed_matching = True
    await session.flush()
    await session.commit()  # get_session does NOT auto-commit; routes must.
    await session.refresh(applicant)  # re-hydrate Postgres-normalized Numeric scale

    response = MeResponse(
        id=user.id,
        email=user.email or "",
        role=user.role.value,
        applicant=ApplicantRead.model_validate(applicant, from_attributes=True),
    )
    if changed_matching:
        _dispatch_score(applicant.id)
    return response
```

- [ ] **Step 4: Register the router**

In `api/src/kpa/app_factory.py`, add the import alongside the other route imports and the include_router call. Find the block ending at line 75 (`app.include_router(notifications.router)`) and the imports. Add `applicants` to the routes import and add this line after `app.include_router(resumes.router)`:

```python
    app.include_router(applicants.router)
```

And in the routes import statement (the `from kpa.routes import (...)` or per-module imports near the top of `create_app`), add `applicants`. Match the existing import style exactly — if it's `from kpa.routes import auth, feed, ...`, add `applicants` to that list; if per-line, add `from kpa.routes import applicants`.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest -v -m integration tests/integration/test_profile_update.py::test_patch_partial_update`
Expected: PASS.

- [ ] **Step 6: Lint + type-check**

Run: `uv run ruff check src/ tests/ && uv run mypy`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add src/kpa/routes/applicants.py src/kpa/app_factory.py tests/integration/test_profile_update.py
git commit -m "feat(api): PATCH /v1/applicants/me profile update"
```

---

## Task 2: Backend — validation, null-clear, 403, extra-forbid

**Files:**
- Test: `api/tests/integration/test_profile_update.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `api/tests/integration/test_profile_update.py`:

```python
async def test_patch_explicit_null_clears_nullable(
    async_client: httpx.AsyncClient, google_verifier, session
) -> None:
    signin = await _signin(async_client, google_verifier)
    access = signin["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    await async_client.patch("/v1/applicants/me", headers=headers, json={"notice_period_days": 30})
    resp = await async_client.patch(
        "/v1/applicants/me", headers=headers, json={"notice_period_days": None}
    )
    assert resp.status_code == 200
    assert resp.json()["applicant"]["notice_period_days"] is None


async def test_patch_omitted_key_unchanged(
    async_client: httpx.AsyncClient, google_verifier
) -> None:
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    await async_client.patch("/v1/applicants/me", headers=headers, json={"notice_period_days": 45})
    resp = await async_client.patch("/v1/applicants/me", headers=headers, json={"locations": ["Pune"]})
    assert resp.status_code == 200
    assert resp.json()["applicant"]["notice_period_days"] == 45


@pytest.mark.parametrize(
    "body",
    [
        {"full_name": ""},
        {"full_name": "x" * 201},
        {"full_name": None},
        {"locations": None},
        {"locations": [""]},
        {"locations": ["a"] * 11},
        {"notice_period_days": -1},
        {"notice_period_days": 400},
        {"current_ctc": -5},
        {"years_experience": 61},
        {"unknown_field": "x"},
    ],
)
async def test_patch_validation_422(
    async_client: httpx.AsyncClient, google_verifier, body
) -> None:
    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}
    resp = await async_client.patch("/v1/applicants/me", headers=headers, json=body)
    assert resp.status_code == 422


async def test_patch_recruiter_returns_403(
    async_client: httpx.AsyncClient, session
) -> None:
    from kpa.auth.tokens import mint_access_token
    from kpa.db.models import User, UserRole

    user = User(email="rec@example.com", role=UserRole.RECRUITER, google_sub="rec-sub")
    session.add(user)
    await session.flush()
    token = mint_access_token(user_id=user.id, role=user.role)

    resp = await async_client.patch(
        "/v1/applicants/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"locations": ["Pune"]},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not_an_applicant"
```

NOTE: confirm the recruiter-token construction matches the canonical pattern in `tests/integration/test_resumes_auth.py` (mint_access_token signature, User constructor kwargs). If `mint_access_token` or the `User`/`UserRole` import path differs, copy that file's exact usage.

- [ ] **Step 2: Run to verify they fail or pass**

Run: `uv run pytest -v -m integration tests/integration/test_profile_update.py`
Expected: the new tests pass if Task 1's model validation is correct. If any 422 case returns 200 (e.g. per-item length not enforced), fix the `Field` constraints in `ProfileUpdate` until all pass. The 403 test exercises `_require_applicant`.

- [ ] **Step 3: Fix any gaps, re-run**

If `test_patch_recruiter_returns_403` fails because creating a recruiter user requires more columns, mirror `tests/integration/test_resumes_auth.py`'s recruiter setup exactly.

Run: `uv run pytest -v -m integration tests/integration/test_profile_update.py`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_profile_update.py
git commit -m "test(api): profile PATCH validation, null-clear, 403"
```

---

## Task 3: Backend — rescore dispatch assertion

**Files:**
- Test: `api/tests/integration/test_profile_update.py` (append)

- [ ] **Step 1: Write the failing tests**

Append:

```python
async def test_patch_matching_field_dispatches_rescore(
    async_client: httpx.AsyncClient, google_verifier, monkeypatch
) -> None:
    import kpa.workers.tasks.score_applicant as score_mod

    calls: list[str] = []
    monkeypatch.setattr(
        score_mod.score_applicant, "delay", lambda aid: calls.append(aid)
    )

    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}

    resp = await async_client.patch(
        "/v1/applicants/me", headers=headers, json={"locations": ["Pune"]}
    )
    assert resp.status_code == 200
    assert calls == [signin["user"]["applicant_id"]]


async def test_patch_non_matching_field_no_rescore(
    async_client: httpx.AsyncClient, google_verifier, monkeypatch
) -> None:
    import kpa.workers.tasks.score_applicant as score_mod

    calls: list[str] = []
    monkeypatch.setattr(
        score_mod.score_applicant, "delay", lambda aid: calls.append(aid)
    )

    signin = await _signin(async_client, google_verifier)
    headers = {"Authorization": f"Bearer {signin['access_token']}"}

    # notice_period_days is informational — no matching impact.
    resp = await async_client.patch(
        "/v1/applicants/me", headers=headers, json={"notice_period_days": 30}
    )
    assert resp.status_code == 200
    assert calls == []
```

- [ ] **Step 2: Run to verify**

Run: `uv run pytest -v -m integration tests/integration/test_profile_update.py::test_patch_matching_field_dispatches_rescore tests/integration/test_profile_update.py::test_patch_non_matching_field_no_rescore`
Expected: PASS (Task 1 already implements `changed_matching` gating).

- [ ] **Step 3: Full backend gate**

Run: `uv run pytest -q -m integration tests/integration/test_profile_update.py && uv run ruff check src/ tests/ && uv run mypy`
Expected: all PASS, no lint/type errors.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_profile_update.py
git commit -m "test(api): profile PATCH rescore-dispatch gating"
```

---

## Task 4: App — ProfileUpdateDto

**Files:**
- Create: `app/lib/data/me/profile_update_dto.dart`
- Test: `app/test/unit/data/me/profile_update_dto_test.dart`

All commands run from `app/`.

- [ ] **Step 1: Create the DTO**

Create `app/lib/data/me/profile_update_dto.dart`:

```dart
import 'package:json_annotation/json_annotation.dart';

part 'profile_update_dto.g.dart';

/// Request body for PATCH /v1/applicants/me. The edit form owns the full
/// editable set, so all keys are sent every save — including explicit nulls
/// for cleared fields (default includeIfNull: true), so clearing persists.
/// `full_name`/`locations` are always non-null from the form.
@JsonSerializable(createFactory: false)
class ProfileUpdateDto {
  const ProfileUpdateDto({
    required this.fullName,
    required this.locations,
    this.noticePeriodDays,
    this.currentCtc,
    this.expectedCtc,
    this.yearsExperience,
  });

  @JsonKey(name: 'full_name')
  final String fullName;
  final List<String> locations;
  @JsonKey(name: 'notice_period_days')
  final int? noticePeriodDays;
  // Sent as JSON numbers; the backend's Decimal fields coerce from number.
  @JsonKey(name: 'current_ctc')
  final num? currentCtc;
  @JsonKey(name: 'expected_ctc')
  final num? expectedCtc;
  @JsonKey(name: 'years_experience')
  final num? yearsExperience;

  Map<String, dynamic> toJson() => _$ProfileUpdateDtoToJson(this);
}
```

- [ ] **Step 2: Generate code**

Run: `dart run build_runner build --delete-conflicting-outputs`
Expected: writes `profile_update_dto.g.dart`.

- [ ] **Step 3: Write the test**

Create `app/test/unit/data/me/profile_update_dto_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/me/profile_update_dto.dart';

void main() {
  test('toJson uses snake_case keys and includes explicit nulls', () {
    const dto = ProfileUpdateDto(
      fullName: 'Alice Khan',
      locations: ['Pune', 'Bengaluru'],
      noticePeriodDays: 30,
      currentCtc: 1200000,
      expectedCtc: null,
      yearsExperience: 4.5,
    );
    final json = dto.toJson();

    expect(json['full_name'], 'Alice Khan');
    expect(json['locations'], ['Pune', 'Bengaluru']);
    expect(json['notice_period_days'], 30);
    expect(json['current_ctc'], 1200000);
    expect(json['years_experience'], 4.5);
    // Cleared field is present as an explicit null (so the backend clears it).
    expect(json.containsKey('expected_ctc'), isTrue);
    expect(json['expected_ctc'], isNull);
  });
}
```

- [ ] **Step 4: Run the test**

Run: `flutter test test/unit/data/me/profile_update_dto_test.dart`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/data/me/profile_update_dto.dart lib/data/me/profile_update_dto.g.dart test/unit/data/me/profile_update_dto_test.dart
git commit -m "feat(app): ProfileUpdateDto request body"
```

---

## Task 5: App — MeRepository.updateProfile

**Files:**
- Modify: `app/lib/data/me/me_repository.dart`, `app/lib/data/me/me_api.dart`, `app/lib/data/me/me_repository_impl.dart`
- Modify (fakes): `app/test/helpers/fake_repositories.dart`, `app/test/widget/profile_screen_test.dart`
- Test: `app/test/unit/data/me/me_repository_impl_test.dart` (append)

- [ ] **Step 1: Write the failing test**

Append to `app/test/unit/data/me/me_repository_impl_test.dart` (inside `main()`):

```dart
  test('updateProfile: PATCH sends full set incl nulls → MeDto', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    final mock = MockInterceptor();
    dio.interceptors.add(mock);
    mock.on('PATCH', '/v1/applicants/me', 200, {
      'id': 'u1',
      'email': 'u@e.com',
      'role': 'applicant',
      'applicant': {
        'id': 'a1',
        'full_name': 'Alice Khan',
        'locations': ['Pune'],
        'notice_period_days': null,
      },
    });
    final repo = MeRepositoryImpl(MeApi(dio));
    final me = await repo.updateProfile(
      const ProfileUpdateDto(
        fullName: 'Alice Khan',
        locations: ['Pune'],
        expectedCtc: null,
      ),
    );
    expect(me.applicant?.fullName, 'Alice Khan');
    final sent = mock.lastDataFor('PATCH', '/v1/applicants/me') as Map<String, dynamic>;
    expect(sent['full_name'], 'Alice Khan');
    expect(sent['locations'], ['Pune']);
    expect(sent.containsKey('expected_ctc'), isTrue);
  });
```

Add imports at the top of the test file if missing:
```dart
import 'package:kpa_app/data/me/profile_update_dto.dart';
```

- [ ] **Step 2: Run to verify it fails**

Run: `flutter test test/unit/data/me/me_repository_impl_test.dart`
Expected: FAIL — `updateProfile` not defined.

- [ ] **Step 3: Extend the interface**

Replace `app/lib/data/me/me_repository.dart` contents:

```dart
import 'package:kpa_app/data/me/me_dto.dart';
import 'package:kpa_app/data/me/profile_update_dto.dart';

abstract interface class MeRepository {
  Future<MeDto> fetch();
  Future<MeDto> updateProfile(ProfileUpdateDto update);
}
```

- [ ] **Step 4: Add the API call**

Replace `app/lib/data/me/me_api.dart` contents:

```dart
import 'package:dio/dio.dart';

import 'package:kpa_app/data/me/me_dto.dart';
import 'package:kpa_app/data/me/profile_update_dto.dart';

class MeApi {
  MeApi(this._dio);
  final Dio _dio;

  Future<MeDto> getMe() async {
    final res = await _dio.get<Map<String, dynamic>>('/v1/me');
    return MeDto.fromJson(res.data!);
  }

  Future<MeDto> updateProfile(ProfileUpdateDto update) async {
    final res = await _dio.patch<Map<String, dynamic>>(
      '/v1/applicants/me',
      data: update.toJson(),
    );
    return MeDto.fromJson(res.data!);
  }
}
```

- [ ] **Step 5: Implement in the repository**

In `app/lib/data/me/me_repository_impl.dart`, add the import and the method inside `MeRepositoryImpl`:

```dart
import 'package:kpa_app/data/me/profile_update_dto.dart';
```

```dart
  @override
  Future<MeDto> updateProfile(ProfileUpdateDto update) async {
    try {
      return await _api.updateProfile(update);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }
```

- [ ] **Step 6: Update the test fakes (interface grew)**

In `app/test/helpers/fake_repositories.dart`, add to `FakeMeRepository` (and add the import `import 'package:kpa_app/data/me/profile_update_dto.dart';`):

```dart
  @override
  Future<MeDto> updateProfile(ProfileUpdateDto update) async => const MeDto(
        id: 'u1',
        email: 'u@e.com',
        displayName: 'U',
        role: 'applicant',
        applicant: ApplicantSummaryDto(id: 'a1', fullName: 'U'),
      );
```

In `app/test/widget/profile_screen_test.dart`, the `_FakeRepo` implements `MeRepository` — add the same `updateProfile` override (import `profile_update_dto.dart`):

```dart
  @override
  Future<MeDto> updateProfile(ProfileUpdateDto update) async => me;
```

- [ ] **Step 7: Generate + run tests**

Run: `dart run build_runner build --delete-conflicting-outputs && flutter test test/unit/data/me/`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add lib/data/me/ test/helpers/fake_repositories.dart test/widget/profile_screen_test.dart test/unit/data/me/me_repository_impl_test.dart
git commit -m "feat(app): MeRepository.updateProfile (PATCH applicants/me)"
```

---

## Task 6: App — ProfileEditController

**Files:**
- Create: `app/lib/presentation/profile/profile_edit_controller.dart`
- Test: `app/test/unit/presentation/profile/profile_edit_controller_test.dart`

- [ ] **Step 1: Create the controller**

Create `app/lib/presentation/profile/profile_edit_controller.dart`:

```dart
import 'dart:async';

import 'package:kpa_app/data/me/me_repository_impl.dart';
import 'package:kpa_app/data/me/profile_update_dto.dart';
import 'package:kpa_app/presentation/profile/me_controller.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'profile_edit_controller.g.dart';

@riverpod
class ProfileEditController extends _$ProfileEditController {
  @override
  FutureOr<void> build() {}

  /// Submit the edit. Returns true on success (and invalidates the cached me),
  /// false on error (state carries the error for the UI to surface).
  Future<bool> submit(ProfileUpdateDto update) async {
    state = const AsyncValue.loading();
    final result = await AsyncValue.guard(
      () => ref.read(meRepositoryProvider).updateProfile(update),
    );
    if (result.hasError) {
      state = AsyncValue.error(result.error!, result.stackTrace!);
      return false;
    }
    state = const AsyncValue.data(null);
    ref.invalidate(meControllerProvider);
    return true;
  }
}
```

- [ ] **Step 2: Generate code**

Run: `dart run build_runner build --delete-conflicting-outputs`
Expected: writes `profile_edit_controller.g.dart`. Confirm the generated provider name is `profileEditControllerProvider` (Riverpod 4 drops the `Controller`→`Notifier` suffix conventions; check the `.g.dart`).

- [ ] **Step 3: Write the test**

Create `app/test/unit/presentation/profile/profile_edit_controller_test.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/me/me_dto.dart';
import 'package:kpa_app/data/me/me_repository.dart';
import 'package:kpa_app/data/me/me_repository_impl.dart';
import 'package:kpa_app/data/me/profile_update_dto.dart';
import 'package:kpa_app/presentation/profile/profile_edit_controller.dart';

class _OkRepo implements MeRepository {
  @override
  Future<MeDto> fetch() async => const MeDto(id: 'u1', email: 'e', role: 'applicant');
  @override
  Future<MeDto> updateProfile(ProfileUpdateDto u) async =>
      const MeDto(id: 'u1', email: 'e', role: 'applicant');
}

class _ErrRepo implements MeRepository {
  @override
  Future<MeDto> fetch() async => const MeDto(id: 'u1', email: 'e', role: 'applicant');
  @override
  Future<MeDto> updateProfile(ProfileUpdateDto u) async =>
      throw const ApiException(statusCode: 422, slug: 'bad');
}

const _update = ProfileUpdateDto(fullName: 'A', locations: ['Pune']);

void main() {
  test('submit success returns true', () async {
    final c = ProviderContainer(
      overrides: [meRepositoryProvider.overrideWithValue(_OkRepo())],
    );
    addTearDown(c.dispose);
    final ok = await c.read(profileEditControllerProvider.notifier).submit(_update);
    expect(ok, isTrue);
  });

  test('submit error returns false and sets error state', () async {
    final c = ProviderContainer(
      overrides: [meRepositoryProvider.overrideWithValue(_ErrRepo())],
    );
    addTearDown(c.dispose);
    final ok = await c.read(profileEditControllerProvider.notifier).submit(_update);
    expect(ok, isFalse);
    expect(c.read(profileEditControllerProvider).hasError, isTrue);
  });
}
```

- [ ] **Step 4: Run the test**

Run: `flutter test test/unit/presentation/profile/profile_edit_controller_test.dart`
Expected: PASS. If the provider name differs, update the test to the generated name from Step 2.

- [ ] **Step 5: Commit**

```bash
git add lib/presentation/profile/profile_edit_controller.dart lib/presentation/profile/profile_edit_controller.g.dart test/unit/presentation/profile/profile_edit_controller_test.dart
git commit -m "feat(app): ProfileEditController"
```

---

## Task 7: App — CTC formatting + Profile read-only details

**Files:**
- Create: `app/lib/presentation/profile/ctc_format.dart`
- Modify: `app/lib/presentation/profile/profile_screen.dart`
- Modify: `app/test/widget/profile_screen_test.dart`
- Test: `app/test/unit/presentation/profile/ctc_format_test.dart`

- [ ] **Step 1: Create the formatter + test**

Create `app/lib/presentation/profile/ctc_format.dart`:

```dart
import 'package:intl/intl.dart';

// Module-static: NumberFormat parses its pattern on construction.
final _inr = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 0);

/// Format a wire CTC string (Pydantic Decimal → JSON string) as Indian-grouped
/// rupees. Returns '—' for null/unparseable.
String formatCtc(String? raw) {
  if (raw == null) return '—';
  final v = double.tryParse(raw);
  if (v == null) return '—';
  return _inr.format(v);
}
```

Create `app/test/unit/presentation/profile/ctc_format_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/presentation/profile/ctc_format.dart';

void main() {
  test('formats Indian-grouped rupees', () {
    expect(formatCtc('1200000.00'), '₹12,00,000');
  });
  test('null and unparseable → dash', () {
    expect(formatCtc(null), '—');
    expect(formatCtc('abc'), '—');
  });
}
```

- [ ] **Step 2: Run formatter test**

Run: `flutter test test/unit/presentation/profile/ctc_format_test.dart`
Expected: PASS. (If the grouped output differs by a non-breaking space or symbol placement, adjust the expected string to match intl's actual `en_IN` output — run once and read the actual value.)

- [ ] **Step 3: Add read-only details + Edit button to Profile screen**

In `app/lib/presentation/profile/profile_screen.dart`:

Add imports:
```dart
import 'package:go_router/go_router.dart';
import 'package:kpa_app/presentation/profile/ctc_format.dart';
import 'package:kpa_app/presentation/routing/routes.dart';
```

Change the `AppBar` to include an Edit action:
```dart
      appBar: AppBar(
        title: const Text('Profile'),
        actions: [
          TextButton(
            onPressed: () => context.go(Routes.profileEdit),
            child: const Text('Edit'),
          ),
        ],
      ),
```

After the email `Text` (the block ending around line 39) and before the existing `Text('Account', ...)`, insert a details section built from `data.applicant`:

```dart
            if (data.applicant case final a?) ...[
              const SizedBox(height: KpaSpacing.xl),
              _DetailRow(label: 'Locations', value: a.locations.isEmpty ? '—' : a.locations.join(', ')),
              if (a.yearsExperience != null)
                _DetailRow(label: 'Experience', value: '${a.yearsExperience} yrs'),
              if (a.noticePeriodDays != null)
                _DetailRow(label: 'Notice period', value: '${a.noticePeriodDays} days'),
              _DetailRow(label: 'Current CTC', value: formatCtc(a.currentCtc)),
              _DetailRow(label: 'Expected CTC', value: formatCtc(a.expectedCtc)),
            ],
```

Add a `_DetailRow` widget at the bottom of the file (after `ProfileScreen`'s class, sibling to the existing private helpers):

```dart
class _DetailRow extends StatelessWidget {
  const _DetailRow({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: KpaSpacing.xs),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 120,
            child: Text(
              label,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
          Expanded(child: Text(value, style: theme.textTheme.bodyMedium)),
        ],
      ),
    );
  }
}
```

NOTE: `ApplicantSummaryDto` exposes `locations` (List<String>), `yearsExperience`/`currentCtc`/`expectedCtc` (String?), `noticePeriodDays` (int?) — confirm against `lib/data/me/me_dto.dart` before wiring.

- [ ] **Step 4: Update the profile widget test**

In `app/test/widget/profile_screen_test.dart`, the seeded `MeDto` currently has `applicant: ApplicantSummaryDto(id: 'a1', fullName: 'Eng U')`. Extend it so the detail rows render, and add an assertion. Change the construction to:

```dart
      const me = MeDto(
        id: 'u1',
        email: 'eng@example.com',
        displayName: 'Eng U',
        role: 'applicant',
        applicant: ApplicantSummaryDto(
          id: 'a1',
          fullName: 'Eng U',
          locations: ['Pune'],
          expectedCtc: '1800000.00',
        ),
      );
```

After the existing pump/assertions, add:
```dart
      expect(find.text('Locations'), findsOneWidget);
      expect(find.text('Pune'), findsOneWidget);
      expect(find.text('Edit'), findsOneWidget);
```

NOTE: the widget test wraps the screen in a router-less `MaterialApp`. `context.go(...)` needs a GoRouter in the tree. Tapping isn't tested here (only presence of 'Edit'); if the build throws because `Routes.profileEdit`/go is referenced at build time, it won't (it's only invoked on tap). Leave tap-navigation to the integration test. If the test harness lacks `go_router` context and the button's mere presence triggers an error, wrap the test's `MaterialApp` with a minimal `GoRouter` (see `test/integration/golden_path_test.dart` for the app's router setup) — otherwise leave as-is.

- [ ] **Step 5: Run tests**

Run: `flutter test test/unit/presentation/profile/ctc_format_test.dart test/widget/profile_screen_test.dart`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add lib/presentation/profile/ctc_format.dart lib/presentation/profile/profile_screen.dart test/unit/presentation/profile/ctc_format_test.dart test/widget/profile_screen_test.dart
git commit -m "feat(app): profile read-only details + CTC formatting"
```

---

## Task 8: App — EditProfileScreen + route

**Files:**
- Create: `app/lib/presentation/profile/edit_profile_screen.dart`
- Modify: `app/lib/presentation/routing/routes.dart`, `app/lib/presentation/routing/router.dart`
- Test: `app/test/widget/edit_profile_screen_test.dart`

- [ ] **Step 1: Add the route constant**

In `app/lib/presentation/routing/routes.dart`, add inside `Routes`:

```dart
  static const profileEdit = '/profile/edit';
```

- [ ] **Step 2: Register the nested route**

In `app/lib/presentation/routing/router.dart`, replace the profile `GoRoute` (lines 113-116) with:

```dart
              GoRoute(
                path: Routes.profile,
                builder: (_, __) => const ProfileScreen(),
                routes: [
                  GoRoute(
                    path: 'edit',
                    builder: (_, __) => const EditProfileScreen(),
                  ),
                ],
              ),
```

Add the import:
```dart
import 'package:kpa_app/presentation/profile/edit_profile_screen.dart';
```

- [ ] **Step 3: Create the EditProfileScreen**

Create `app/lib/presentation/profile/edit_profile_screen.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:kpa_app/data/me/profile_update_dto.dart';
import 'package:kpa_app/presentation/profile/me_controller.dart';
import 'package:kpa_app/presentation/profile/profile_edit_controller.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';

class EditProfileScreen extends ConsumerStatefulWidget {
  const EditProfileScreen({super.key});
  @override
  ConsumerState<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends ConsumerState<EditProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _fullName;
  late final TextEditingController _experience;
  late final TextEditingController _notice;
  late final TextEditingController _currentCtc;
  late final TextEditingController _expectedCtc;
  final _locationInput = TextEditingController();
  late List<String> _locations;

  @override
  void initState() {
    super.initState();
    final a = ref.read(meControllerProvider).valueOrNull?.applicant;
    _fullName = TextEditingController(text: a?.fullName ?? '');
    _experience = TextEditingController(text: a?.yearsExperience ?? '');
    _notice = TextEditingController(text: a?.noticePeriodDays?.toString() ?? '');
    _currentCtc = TextEditingController(text: a?.currentCtc ?? '');
    _expectedCtc = TextEditingController(text: a?.expectedCtc ?? '');
    _locations = List<String>.from(a?.locations ?? const []);
  }

  @override
  void dispose() {
    _fullName.dispose();
    _experience.dispose();
    _notice.dispose();
    _currentCtc.dispose();
    _expectedCtc.dispose();
    _locationInput.dispose();
    super.dispose();
  }

  void _addLocation() {
    final v = _locationInput.text.trim();
    if (v.isEmpty || _locations.contains(v)) return;
    setState(() {
      _locations.add(v);
      _locationInput.clear();
    });
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    final update = ProfileUpdateDto(
      fullName: _fullName.text.trim(),
      locations: _locations,
      noticePeriodDays: int.tryParse(_notice.text.trim()),
      currentCtc: num.tryParse(_currentCtc.text.trim()),
      expectedCtc: num.tryParse(_expectedCtc.text.trim()),
      yearsExperience: num.tryParse(_experience.text.trim()),
    );
    final ok = await ref
        .read(profileEditControllerProvider.notifier)
        .submit(update);
    if (!mounted) return;
    if (ok) {
      if (context.canPop()) context.pop();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Couldn't save. Try again.")),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final saving = ref.watch(profileEditControllerProvider).isLoading;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Edit Profile'),
        actions: [
          TextButton(
            onPressed: saving ? null : _save,
            child: Text(saving ? 'Saving…' : 'Save'),
          ),
        ],
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(KpaSpacing.lg),
          children: [
            TextFormField(
              controller: _fullName,
              decoration: const InputDecoration(labelText: 'Full name'),
              validator: (v) =>
                  (v == null || v.trim().isEmpty) ? 'Required' : null,
            ),
            const SizedBox(height: KpaSpacing.lg),
            Text('Locations', style: Theme.of(context).textTheme.labelLarge),
            Wrap(
              spacing: KpaSpacing.sm,
              children: [
                for (final loc in _locations)
                  Chip(
                    label: Text(loc),
                    onDeleted: () => setState(() => _locations.remove(loc)),
                  ),
              ],
            ),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _locationInput,
                    decoration: const InputDecoration(labelText: 'Add location'),
                    onSubmitted: (_) => _addLocation(),
                  ),
                ),
                IconButton(onPressed: _addLocation, icon: const Icon(Icons.add)),
              ],
            ),
            const SizedBox(height: KpaSpacing.lg),
            TextFormField(
              controller: _experience,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(labelText: 'Years of experience'),
            ),
            TextFormField(
              controller: _notice,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Notice period (days)'),
            ),
            TextFormField(
              controller: _currentCtc,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Current CTC (₹/yr)'),
            ),
            TextFormField(
              controller: _expectedCtc,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Expected CTC (₹/yr)'),
            ),
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 4: Write the widget test**

Create `app/test/widget/edit_profile_screen_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/me/me_dto.dart';
import 'package:kpa_app/data/me/me_repository.dart';
import 'package:kpa_app/data/me/me_repository_impl.dart';
import 'package:kpa_app/data/me/profile_update_dto.dart';
import 'package:kpa_app/presentation/profile/edit_profile_screen.dart';
import 'package:kpa_app/presentation/profile/me_controller.dart';

class _CapturingRepo implements MeRepository {
  ProfileUpdateDto? captured;
  @override
  Future<MeDto> fetch() async => const MeDto(
        id: 'u1',
        email: 'e@e.com',
        role: 'applicant',
        applicant: ApplicantSummaryDto(
          id: 'a1',
          fullName: 'Alice',
          locations: ['Pune'],
        ),
      );
  @override
  Future<MeDto> updateProfile(ProfileUpdateDto update) async {
    captured = update;
    return fetch();
  }
}

void main() {
  testWidgets('renders seeded values, adds a chip, saves', (tester) async {
    final repo = _CapturingRepo();
    final container = ProviderContainer(
      overrides: [meRepositoryProvider.overrideWithValue(repo)],
    );
    addTearDown(container.dispose);
    // Warm the me cache so initState reads seeded values.
    await container.read(meControllerProvider.future);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: EditProfileScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Pune'), findsOneWidget); // seeded chip

    await tester.enterText(find.widgetWithText(TextField, 'Add location'), 'Mumbai');
    await tester.tap(find.byIcon(Icons.add));
    await tester.pump();
    expect(find.text('Mumbai'), findsOneWidget);

    await tester.tap(find.widgetWithText(TextButton, 'Save'));
    await tester.pumpAndSettle();

    expect(repo.captured, isNotNull);
    expect(repo.captured!.fullName, 'Alice');
    expect(repo.captured!.locations, ['Pune', 'Mumbai']);
  });
}
```

NOTE: `EditProfileScreen` calls `context.pop()` on success. Under a bare `MaterialApp` (no GoRouter), `context.pop()` resolves to Navigator.pop on an empty stack — harmless in the test (nothing to pop) but if it throws, wrap `home:` in a `Navigator`-providing route or assert before the pop by checking `repo.captured` (already done). If `context.pop()` errors, change the screen's success branch to `if (context.canPop()) context.pop();` and re-run.

- [ ] **Step 5: Run the test**

Run: `flutter test test/widget/edit_profile_screen_test.dart`
Expected: PASS.

- [ ] **Step 6: Full app gate**

Run: `flutter analyze lib test && flutter test && dart format lib test`
Expected: no analyzer errors/warnings (pre-existing infos ok); all tests pass.

- [ ] **Step 7: Commit**

```bash
git add lib/presentation/profile/edit_profile_screen.dart lib/presentation/routing/routes.dart lib/presentation/routing/router.dart test/widget/edit_profile_screen_test.dart
git commit -m "feat(app): EditProfileScreen + /profile/edit route"
```

---

## Final verification

- [ ] Backend: `cd api && uv run pytest -q -m integration && uv run ruff check src/ tests/ && uv run mypy`
- [ ] App: `cd app && flutter analyze lib test && flutter test`
- [ ] Manual (optional): run the app, sign in, open Profile → Edit, change locations + expected CTC, Save → returns to Profile showing updated values; backend logs show a `score.dispatch-failed` only if the broker is down, else a queued `kpa.score_applicant`.
