# P4 Sub-project F — Flutter consent screens (DPDP UI)

**Status:** approved 2026-05-29 (autonomous; user explicitly said "start consent screen F")
**Owner:** frontend
**Scope:** the user-facing UI for the consent + DSR endpoints shipped by PRs #26, #27, #28.

## 1. Why this slice exists

Without a UI, the backend endpoints from sub-projects B/C/D are unreachable to applicants. DPDP-Act-2023 § 7 requires the consent withdrawal mechanism be "as easy as" the grant mechanism — meaning a UI surface, not a curl invocation. This slice closes the legal loop on the user-facing side.

## 2. Non-goals

- Recruiter-side consent UI. Recruiters can call the endpoints today; their consent flow lives in a future recruiter-app slice. For v0 the screen renders for recruiters too (same endpoints) but isn't a polished recruiter UX.
- Cross-platform native "save data export" — see § 5 below; v0 uses Clipboard.
- Server-side rate limiting (deferred to backend follow-up).
- An "I changed my mind" 30-day delete grace window — backend doesn't support it either; deferred together.
- A separate flow for OAuth account de-linking. Today there's only Google; OAuth-identity rows are wiped by DSR-delete.
- In-app translations / localization (spec § 3.7 of the engineering spec; the app is en-only for v0).

## 3. Screens + navigation

### 3.1 Routes

Two new routes, both under the Profile tab branch:

```
/profile/privacy        → PrivacyScreen (consents + DSR controls)
/profile/privacy/delete → DeleteAccountScreen
```

The Profile screen gets a new ListTile, between "Notifications" and "Sign out":

```
ListTile(
  leading: Icon(Icons.shield_outlined),
  title: Text('Privacy & data'),
  subtitle: Text('Notification preferences, export, delete'),
  onTap: () => context.go(Routes.privacy),
)
```

### 3.2 PrivacyScreen layout

One scrollable column, three sections:

```
─────────────────────────
 Notification preferences
─────────────────────────
 [✓] Service updates             ← email_transactional
     Email about your applications, matches, and account.
 [ ] Job recommendations         ← email_marketing
     Weekly digest of jobs that fit your profile.
 [✓] In-app notifications        ← in_app_notifications
     See alerts inside the app.

─────────────────────────
 Your data
─────────────────────────
 [ Download my data ]
     A copy of everything we know about you (JSON).

─────────────────────────
 Account
─────────────────────────
 [ Delete my account ]            ← red destructive button
     Permanently erase your data. This can't be undone.
```

Reserved scopes (`whatsapp_notifications`, `sms_notifications`, `profile_visibility_recruiters`, `third_party_sharing_recruiters`) are **NOT rendered**. They have no UI gate-on today, and showing four greyed-out toggles is worse than hiding them.

### 3.3 DeleteAccountScreen layout

```
─────────────────────────
 Delete my account
─────────────────────────

 ⚠ This will permanently delete your personal data
   on KPA. This action is irreversible.

 What will happen:
 • Your profile, resume, applications, and saved jobs are removed.
 • Your match history and notifications are erased.
 • Anonymized employer-side analytics survive (apply counts only).

 → Before you continue, [Download my data] ← if not already exported

 To confirm, type DELETE_MY_ACCOUNT below:
 ┌─────────────────────────────────────┐
 │                                     │
 └─────────────────────────────────────┘

 [ Delete my account ]   ← disabled until field == "DELETE_MY_ACCOUNT"
 [ Cancel ]
```

On submit:
1. Show modal: "Are you absolutely sure? Yes / Cancel".
2. On Yes: call `DELETE /v1/me/dsr` with `{"confirmation": "DELETE_MY_ACCOUNT"}`.
3. On 200: clear the AccessTokenHolder, trigger sign-out (which the existing `SignedOut` state already routes to `/signin`), and show a one-time snackbar on the sign-in screen: "Your account has been deleted."
4. On error: snackbar with the error message; field stays filled so user can retry.

## 4. Consent state management

### 4.1 Controller

`PrivacyController` is a `@Riverpod` keepAlive notifier:

```dart
@riverpod
class PrivacyController extends _$PrivacyController {
  @override
  Future<PrivacyState> build() async {
    final repo = ref.read(consentsRepositoryProvider);
    final consents = await repo.list();
    return PrivacyState(consents: consents.items);
  }

  Future<void> setConsent(ConsentScope scope, bool granted) async {
    // Optimistic update + PATCH + rollback on error.
  }
}
```

`PrivacyState`:

```dart
@freezed
class PrivacyState with _$PrivacyState {
  const factory PrivacyState({
    required List<ConsentDto> consents,
    Object? mutationError,
  }) = _PrivacyState;
}
```

### 4.2 Optimistic toggles + rollback

On toggle:
1. Set `AsyncValue.data(state.copyWith(consents: optimisticList))` immediately.
2. Call `repo.patchConsent(scope, granted)`.
3. On success: replace the optimistic item with the server's response (canonical `updated_at`).
4. On error: revert to the original list, surface `mutationError` so the screen shows a snackbar.

### 4.3 `email_transactional` warning

If the user toggles `email_transactional` **off**, show a confirmation dialog BEFORE calling the PATCH:

> "Turn off service emails?
>
> You won't receive emails about your applications, matches, or account. Are you sure?
>
> [ Cancel ] [ Turn off ]"

Only proceed if "Turn off" is tapped. Other toggles don't get this guard.

## 5. DSR export — "Download my data" UX

### 5.1 What happens on tap

1. Loading spinner overlay (modal barrier).
2. `dsrRepository.exportData()` calls `POST /v1/me/dsr/export`.
3. The response is the JSON envelope as a String.
4. **On success:** copy the envelope to the system clipboard via `Clipboard.setData(ClipboardData(text: envelope))`.
5. Show a multi-line snackbar:
   > "Your data is on your clipboard.
   > Paste it into a text editor and save as a .json file."
6. Dismiss the spinner.

### 5.2 Why clipboard (and not native file save)

Trade-offs (per spec § 2 non-goals):
- **Native save on iOS/Android:** requires `path_provider` + `share_plus` + iOS Info.plist + Android FileProvider config. Adds ~200 KB and one round of Xcode/Gradle config.
- **Web download:** requires `package:web` Blob API behind a conditional import per the existing GoogleSignIn pattern.
- **Clipboard:** works on every platform with `Flutter.services.Clipboard`, zero new deps.

For v0, clipboard is acceptable. Document in CLAUDE.md as a v0 limitation; the follow-up "DSR export native save" task is tracked in the PR description.

### 5.3 Large-payload behavior

The envelope can be hundreds of KB. The system clipboard accepts that on every platform we target. If size becomes a problem (an applicant with > 10 K audit rows), we switch to async backend + signed-URL per the DSR-export spec § 5 — at which point the UI swaps to "Email me a link" anyway.

## 6. DSR delete — flow specifics

### 6.1 Confirmation field

A `TextField` with `controller`. The "Delete my account" submit button watches the controller's value:

```dart
ValueListenableBuilder(
  valueListenable: _confirmationController,
  builder: (_, value, __) {
    final enabled = value.text == 'DELETE_MY_ACCOUNT';
    return FilledButton(
      style: FilledButton.styleFrom(
        backgroundColor: theme.colorScheme.error,
      ),
      onPressed: enabled ? () => _attemptDelete(context) : null,
      child: Text('Delete my account'),
    );
  },
)
```

The check is case-sensitive, exact match. Typos disable the button.

### 6.2 Post-delete flow

After 200 from `DELETE /v1/me/dsr`:
1. `AccessTokenHolder.clear()` so subsequent requests don't carry the stale token.
2. Push `SignedOut` to `authStateProvider`. The router's existing redirect handles the navigation to `/signin`.
3. Set a one-time flag (a Riverpod provider) `deleteSuccessSnackbarProvider` so the sign-in screen shows a snackbar exactly once.

### 6.3 Error handling

- 400 `confirmation_mismatch` — shouldn't happen because the UI guards against it. If it does (race condition between optimistic UI and server validation), show an inline error and keep the form open.
- 401 — the token expired. The refresh interceptor handles it transparently; if refresh also fails, the user is signed out anyway.
- 5xx / network — snackbar "Couldn't delete your account. Try again." with the request_id from the response.

## 7. Data layer

### 7.1 DTOs

`lib/data/consents/consent_dto.dart`:

```dart
@JsonSerializable()
class ConsentDto {
  final String scope;       // raw string from server; Dart-side enum lookup in presentation layer
  final bool granted;
  @JsonKey(name: 'updated_at')
  final DateTime updatedAt;
  ConsentDto(...);
  factory ConsentDto.fromJson(Map<String, dynamic> json) => _$ConsentDtoFromJson(json);
  Map<String, dynamic> toJson() => _$ConsentDtoToJson(this);
}

@JsonSerializable()
class ConsentListResponse {
  final List<ConsentDto> items;
  ConsentListResponse(this.items);
  factory ConsentListResponse.fromJson(Map<String, dynamic> json) => _$ConsentListResponseFromJson(json);
}
```

`scope` stays as `String` at the DTO layer (mirroring the backend's `TEXT` choice). Dart-side `ConsentScope` enum lives in `lib/core/consent/consent_scope.dart` with the seven values (mirror the backend StrEnum); the presentation layer maps `dto.scope → ConsentScope?` and ignores unknown values gracefully (defense against backend adding a new scope).

### 7.2 DSR

`lib/data/dsr/dsr_api.dart`:

```dart
class DsrApi {
  DsrApi(this._dio);
  final Dio _dio;

  /// Returns the export envelope as a JSON string (not parsed).
  /// We don't parse it Dart-side because (a) we'd need 18 Dart row models,
  /// and (b) the contract is "give me the JSON" — we just relay it.
  Future<String> exportData() async {
    final res = await _dio.post<String>(
      '/v1/me/dsr/export',
      options: Options(responseType: ResponseType.plain),
    );
    return res.data!;
  }

  Future<DsrDeleteResponse> deleteAccount() async {
    final res = await _dio.delete<Map<String, dynamic>>(
      '/v1/me/dsr',
      data: {'confirmation': 'DELETE_MY_ACCOUNT'},
    );
    return DsrDeleteResponse.fromJson(res.data!);
  }
}
```

`DsrDeleteResponse` is a `@JsonSerializable` with `deletedAt`, `sectionCounts`, `warnings`. The warnings model is `OwnerlessEmployerWarning`-shaped on the Dart side.

### 7.3 Repositories

Two abstract interfaces + impls, mirroring the existing `notifications` pattern:

- `ConsentsRepository` / `ConsentsRepositoryImpl` (`list()`, `patch(scope, granted)`)
- `DsrRepository` / `DsrRepositoryImpl` (`exportData()`, `deleteAccount()`)

Each gets a `@riverpod` provider that wires the API + dio.

## 8. Tests

### 8.1 Unit tests

- `test/unit/data/consents/consents_repository_impl_test.dart` — happy path GET + PATCH using `MockInterceptor` from `test/helpers/`.
- `test/unit/data/dsr/dsr_repository_impl_test.dart` — happy path + 400 confirmation_mismatch + 500 error mapping.

### 8.2 Widget tests

- `test/widget/presentation/privacy/privacy_screen_test.dart` — renders 3 toggles in initial state from a fake `ConsentsRepository`; tapping a toggle triggers the fake repo's `patch`.
- `test/widget/presentation/privacy/delete_account_screen_test.dart` — submit button disabled when typed wrong; enabled when typed correctly; tapping triggers fake delete call.

### 8.3 Test fakes

Add `FakeConsentsRepository` and `FakeDsrRepository` to `test/helpers/fake_repositories.dart`.

## 9. CLAUDE.md updates

Add to the "Flutter app (`app/`)" section's "Non-obvious bits" list:

```
- **Privacy screen lives in `presentation/privacy/`.** Single screen combines consent toggles + DSR export + DSR delete navigation. Reserved consent scopes (whatsapp_notifications, sms_notifications, profile_visibility_recruiters, third_party_sharing_recruiters) are deliberately HIDDEN — they have no Dart-side gate today; showing four greyed-out toggles is worse than hiding.
- **DSR export uses the system clipboard** in v0 — `Clipboard.setData(ClipboardData(text: envelope))`. Native file-save is deferred to a follow-up so we don't pull in `share_plus` / `path_provider` / Web Blob API behind a conditional import. Document this in the snackbar copy.
- **DSR delete flow is a separate screen** at `/profile/privacy/delete` with a `DELETE_MY_ACCOUNT` text-confirmation guard. Submit button is disabled until the controller's value exactly matches. On success: clear `AccessTokenHolder`, push `SignedOut` (router redirects to `/signin`), one-time snackbar via `deleteSuccessSnackbarProvider`.
- **Turning OFF `email_transactional`** triggers a confirmation dialog because the user is opting out of service-critical email. Other consent toggles flip without confirmation.
```

## 10. Acceptance

- `/profile/privacy` route renders three toggles + Download button + Delete navigation; reserved scopes hidden.
- Toggling `email_marketing` → optimistic update + PATCH → server response replaces optimistic state.
- Toggling `email_transactional` OFF → confirmation dialog; only proceeds on confirm.
- Download my data → spinner → clipboard write → snackbar.
- Delete my account → typed-confirmation guard → submit → 200 → AccessTokenHolder cleared + SignedOut pushed → router redirects to `/signin` → snackbar shown once.
- All existing widget + unit tests still pass.
- New widget tests for both screens pass.
- New unit tests for both repos pass.
- CLAUDE.md updated per § 9.
- `dart run build_runner build --delete-conflicting-outputs` produces no diff on second run.
