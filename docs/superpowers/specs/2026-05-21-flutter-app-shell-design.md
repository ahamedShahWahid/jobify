# Flutter App Shell — Design

**Status:** Approved (brainstorm 2026-05-21). Awaiting implementation plan.
**Author:** Claude + Ahamed
**Phase:** First slice of the Flutter mobile + web client. Not aligned with backend P-numbering.
**Branch:** `feat/app-shell-foundation`

## Summary

This plan introduces a new top-level `app/` Flutter package as the sibling of `api/`. It builds the **foundation** that every future Flutter feature will depend on (token lifecycle, API client, routing, theming, state primitives, test patterns) and exercises that foundation through **seven thin screens** wired against the existing `/v1` endpoints: splash, sign-in, feed, job detail, applications, saved, profile.

"Shell" here means *foundation + thin flows* — production-quality cross-cutting infrastructure, minimum-viable individual screens. The shell is **not** a polished v0; visual polish, localization, analytics, crash reporting, and notifications UI are explicit non-goals deferred to later plans.

The codebase follows **Pragmatic Clean Architecture** with three top-level layers (`data/`, `domain/`, `presentation/`) plus a `core/` for framework-agnostic infrastructure. Layering is preferred over feature-first co-location per established user preference.

## Goals

1. A buildable, runnable Flutter app on iOS, Android, and Web that signs the user in via Google, lists matched jobs, opens job details, and supports the apply / withdraw / save / unsave mutations against existing `/v1` endpoints.
2. Cross-cutting foundation worth keeping: dio + freezed + Riverpod + go_router wired together correctly once; a single-flight refresh interceptor that handles 401s transparently; secure refresh-token storage across all three platforms; design tokens; reusable AsyncValue-driven UI primitives.
3. A test suite that proves the cross-cutting pieces work — repository tests, refresh-interceptor tests, provider tests, widget smoke tests, and one end-to-end golden-path test.
4. A GitHub Actions workflow that runs analyze + format + test on every PR touching `app/**`.

## Non-goals

- **Notifications inbox UI.** Endpoints exist (`GET /v1/notifications`, `POST /v1/notifications/{id}/read`); the UX deserves a dedicated brainstorm.
- **Resume upload + parse-status polling UI.** Likewise; platform-specific file/camera APIs make this its own slice.
- **Rich match-explanation rendering.** Plain text only in v0; no expand/collapse, no LLM-vs-templated badge styling beyond a small generator label.
- **Push notifications** (FCM/APNs), **crash reporting** (Sentry / Crashlytics), **analytics** (Mixpanel / Firebase Analytics), **offline write queue**, **deep linking beyond `/v1/jobs/{id}`**, **localization** (English only; `intl` package present for date formatting only), **dark mode** (plumbed but disabled), **build flavors**, **accessibility audit**, **visual regression / golden file tests**.
- **Recruiter-side surfaces.** Out of this plan entirely; separate brainstorm.
- **Web SEO / SSR.** Flutter web SPA only.

## Stack decisions

| Concern | Choice | Rationale |
|---|---|---|
| State management | **Riverpod 2.x + riverpod_generator** | Compile-safe DI; `AsyncValue` maps onto every API call's loading/error/data; strong testing story with `ProviderContainer`. |
| Targets | **iOS + Android + Web in v0** | Matches the Flutter mobile + web mandate. Postponing web later forces an auth refactor; modest extra cost up front. |
| API client | **dio + freezed + json_serializable** with hand-written models | Small `/v1` surface (~12 endpoints), git-tracked changes, idiomatic Dart. OpenAPI codegen would be verbose without payoff. |
| Project location | **`app/` sibling to `api/`** in this monorepo | Backend + frontend evolve together; one PR can ship endpoint + screen. Renamable later if recruiter app appears. |
| Mutations in shell | **Include apply, withdraw, save, unsave** | Foundation explicitly covers mutation primitives. Without them the first follow-on feature has to retrofit the entire write surface. |
| Navigation | **Tab bar: Feed \| Saved \| Applications \| Profile** | Surfaces read-after-write so mutations are observable. Anticipates BRD's IA. |
| Routing | **go_router + go_router_builder** | Flutter team's official package. `StatefulShellRoute.indexedStack` is the canonical bottom-tab pattern. Code-gen for typed routes matches the Riverpod codegen story. |
| Layering | **Pragmatic Clean Architecture** (`data/` + `domain/` + `presentation/` + `core/`) | Per [[feedback-flutter-layered-architecture]] memory: explicit layered boundaries, no UseCase classes, one freezed model per entity that doubles as DTO + entity. |

## Architecture

### Project layout

```
app/
├── pubspec.yaml
├── analysis_options.yaml             # very_good_analysis ruleset
├── build.yaml                        # riverpod_generator + json_serializable + freezed + go_router_builder
├── README.md
├── lib/
│   ├── main.dart                     # runApp(ProviderScope(child: KpaApp()))
│   ├── app.dart                      # KpaApp widget — ThemeData + Router wiring
│   ├── core/                         # cross-layer infrastructure (no business meaning)
│   │   ├── config/                   # build-time env (KPA_API_BASE_URL, google_client_id) via --dart-define
│   │   ├── error/                    # ApiException, NetworkException, AuthException + AsyncValueX extensions
│   │   └── log/                      # structured logger (`logger` package or hand-rolled)
│   ├── data/                         # outermost layer — talks to the network
│   │   ├── api/                      # dio instance + auth-refresh interceptor + base error mapper
│   │   ├── auth/                     # GoogleSignInDataSource (per-platform), TokenStorage, AuthRepositoryImpl
│   │   ├── feed/                     # FeedApi + FeedRepositoryImpl + FeedItemDto (freezed)
│   │   ├── jobs/                     # JobsApi + JobsRepositoryImpl + JobDto + ApplicationDto + SavedJobDto
│   │   └── me/                       # MeApi + MeRepositoryImpl + MeDto
│   ├── domain/                       # repository contracts; no Flutter, no dio, no Riverpod
│   │   ├── auth/                     # AuthRepository (interface) + AuthState sealed class
│   │   ├── feed/                     # FeedRepository (interface) + FeedPage value type
│   │   ├── jobs/                     # JobsRepository, ApplicationsRepository, SavedJobsRepository interfaces
│   │   └── me/                       # MeRepository interface
│   └── presentation/                 # Flutter + Riverpod
│       ├── routing/                  # GoRouter config, route guards (auth-required redirect)
│       ├── theme/                    # KpaColors, KpaTypography, KpaSpacing, KpaRadii, ThemeData factory
│       ├── widgets/                  # KpaButton, KpaScoreBadge, KpaEmptyState, KpaErrorView, KpaShellScaffold, AsyncValueWidget
│       ├── splash/                   # SplashScreen + bootstrap controller
│       ├── auth/                     # SignInScreen + signInController
│       ├── feed/                     # FeedScreen + feedController (paginated AsyncNotifier)
│       ├── job_detail/               # JobDetailScreen + jobDetailController + ActionBar
│       ├── applications/             # ApplicationsScreen + applicationsController
│       ├── saved/                    # SavedScreen + savedController
│       └── profile/                  # ProfileScreen + signOut action
└── test/
    ├── unit/                         # repository tests; provider tests via ProviderContainer
    ├── widget/                       # one render-smoke test per screen
    └── integration/                  # one golden-path test: sign-in → feed → detail → apply
```

**Layer dependency rules:**
- `core/` depends on nothing of ours.
- `domain/` depends only on `core/`. Pure Dart — no `package:flutter`, no `package:dio`, no `package:riverpod`.
- `data/` depends on `domain/` (satisfies interfaces) + `core/`.
- `presentation/` depends on `domain/` (consumes interfaces) + `core/`.
- Wiring impl → interface happens in `presentation/<feature>/<feature>_providers.dart` Riverpod modules.

**Pragmatic CA cheat:** the freezed model lives in `data/<feature>/` (where the JSON annotations belong) but is passed up freely through `domain/` and `presentation/`. Strict CA would forbid this; we accept it because the alternative (separate DTO + Entity + Mapper) is ~120 lines of mechanical renaming per feature.

### Auth lifecycle

#### Google Sign-In across the three platforms

| Platform | Plugin | Required config |
|---|---|---|
| iOS | `google_sign_in_ios` (transitive via `google_sign_in`) | `GIDClientID` in `Info.plist`; reversed-client-id URL scheme; `serverClientId` parameter at runtime → web client ID. |
| Android | `google_sign_in_android` | SHA-1 fingerprint registered in Google Cloud Console; `serverClientId` parameter at runtime → web client ID. No `google-services.json` (FCM not used). |
| Web | `google_sign_in_web` | `<meta name="google-signin-client_id">` in `web/index.html`, populated from `--dart-define` at build time. Uses Google Identity Services JS. |

All three converge on a Google ID JWT, POSTed to `POST /v1/auth/oauth/google`. The backend's `KPA_GOOGLE_OAUTH_CLIENT_IDS` accepts a CSV — we register iOS + Android + web client IDs there.

#### Token storage

- iOS / Android: `flutter_secure_storage` → keychain / keystore.
- Web: same package — uses Web Crypto API + IndexedDB. Weaker than native keychains but a stronger XSS posture than `localStorage`.
- We persist **only the refresh token** at rest. The access token lives in an in-memory Riverpod provider and is re-minted on cold start via silent refresh. Defends against disk-at-rest attackers obtaining a valid 10-minute access token.

#### dio + interceptors

A single `Dio` instance lives in `data/api/`, exposed via `dioProvider`. Three interceptors, in order:

1. **`AuthHeaderInterceptor`** — adds `Authorization: Bearer <access>` if the access-token provider has a value. Skipped on `/v1/auth/oauth/google` and `/v1/auth/refresh` via `options.extra['skipAuth'] = true`.
2. **`RequestIdInterceptor`** — generates a uuid4 per request, sets `X-Request-Id`, stashes it in `options.extra` so error mapping can attach it to thrown exceptions. Matches backend's correlation handle.
3. **`RefreshOn401Interceptor`** — when a response is 401 with body slug `invalid_access_token`:
   - **Single-flight:** the interceptor holds a `Completer<void>?`. The first 401 sets it and calls `POST /v1/auth/refresh` with the stored refresh token. Subsequent 401s arriving during this `await` queue on the same Completer instead of stampeding.
   - **On refresh success:** store the new refresh token, update `accessTokenProvider`, complete the Completer, replay the original request once with the new access token.
   - **On refresh failure (any 4xx):** clear the refresh token from storage, set `authStateProvider = SignedOut`, complete the Completer with an error, let the router redirect to `/signin`.
   - **On network error during refresh:** original throws `NetworkException`, auth state unchanged.
   - Requests with `skipAuth=true` are not retried on 401.
   - The original request is replayed at most once; if the replay also 401s, surface as `AuthException`.

This interceptor is the single most important piece of code in the foundation; ~80 lines plus tests.

#### Splash bootstrap (cold-start sequence)

`/` is `SplashScreen`. Reachable only on cold start. Behind the platform native splash, runs:

1. Read refresh token from secure storage.
2. If absent → `authStateProvider = SignedOut` → router redirects to `/signin`.
3. If present → `AuthRepository.refreshSession()`:
   - **200:** `authStateProvider = SignedIn(user)` → router redirects to `/feed`.
   - **4xx:** clear storage, `SignedOut`, redirect to `/signin`. (Not an error — normal "needs sign-in" outcome.)
   - **Network error:** stay on splash, render `KpaErrorView` with "Couldn't reach KPA. Check your connection." + Retry button that re-runs the bootstrap.

Bootstrap is **only** invoked from the splash. Background → foreground does NOT re-run it; the refresh interceptor handles expired access tokens lazily on the next API call.

#### Sign-out

User taps **Sign out** on Profile → confirmation dialog → `signOutController.submit()` calls `POST /v1/auth/logout`, clears local secure storage, sets `authStateProvider = SignedOut`. Router redirect-rule pushes to `/signin`. All `keepAlive: false` providers are auto-disposed.

### Repositories — interface in `domain/`, impl in `data/`

Six repository interfaces. Sketched in Dart pseudocode (final signatures fixed at plan-write time):

```dart
// lib/domain/auth/auth_repository.dart
abstract interface class AuthRepository {
  Stream<AuthState> watch();                          // SignedOut | Authenticating | SignedIn(user)
  Future<SignedIn> signInWithGoogle();                // google_sign_in → POST /v1/auth/oauth/google
  Future<void> refreshSession();                      // POST /v1/auth/refresh — called by splash bootstrap
  Future<void> signOut();                             // POST /v1/auth/logout + clear storage
}

abstract interface class FeedRepository {
  Future<FeedPage> fetchPage({String? cursor, int limit = 20});
}

abstract interface class JobsRepository {
  Future<JobDetail> fetchById(String id);
  Future<Application> applyTo(String jobId, {String source = 'feed'});
  Future<SavedJob> save(String jobId);
  Future<void> unsave(String jobId);
}

abstract interface class ApplicationsRepository {
  Future<ApplicationsPage> fetchPage({String? cursor, int limit = 20});
  Future<Application> withdraw(String applicationId);
}

abstract interface class SavedJobsRepository {
  Future<SavedJobsPage> fetchPage({String? cursor, int limit = 20});
}

abstract interface class MeRepository {
  Future<Me> fetch();
}
```

Methods return freezed value objects or throw typed exceptions from `core/error/` (`AuthException`, `ApiException`, `NetworkException`). No `Result<T,E>` wrapper — dio interceptors + Riverpod's `AsyncValue.guard` give the same affordance with less ceremony.

### State management patterns

Three Riverpod patterns, one role each.

**1. Wiring (DI) providers.** One per repository. `keepAlive: true`. Defined in `presentation/<feature>/<feature>_providers.dart`.

```dart
@Riverpod(keepAlive: true)
FeedRepository feedRepository(Ref ref) =>
    FeedRepositoryImpl(ref.read(dioProvider));
```

**2. Read controllers.** AsyncNotifier per screen. Wraps pagination state + fetch action.

```dart
@riverpod
class FeedController extends _$FeedController {
  @override
  Future<FeedState> build() async {
    final page = await ref.read(feedRepositoryProvider).fetchPage();
    return FeedState(items: page.items, cursor: page.nextCursor, hasMore: page.nextCursor != null);
  }
  Future<void> loadMore() async { /* append; flip isLoadingMore */ }
  Future<void> refresh() async { ref.invalidateSelf(); await future; }
}
```

**3. Mutation controllers.** AsyncNotifier with no `build()` work; mutations called as methods.

```dart
@riverpod
class ApplyToJobController extends _$ApplyToJobController {
  @override
  FutureOr<Application?> build(String jobId) => null;       // idle state

  Future<void> submit({String source = 'feed'}) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final app = await ref.read(jobsRepositoryProvider).applyTo(jobId, source: source);
      ref.invalidate(applicationsControllerProvider);        // applications tab refetches when next viewed
      ref.invalidate(jobDetailControllerProvider(jobId));    // detail's action bar flips to "Withdraw"
      return app;
    });
  }
}
```

#### Invalidation matrix

| Mutation | Invalidates | Why |
|---|---|---|
| Apply to job | `applicationsController`, `jobDetailController(id)` | Applications list updates; detail action bar flips. |
| Withdraw | `applicationsController`, `jobDetailController(id)` | List re-sorts; detail flips back to "Apply". |
| Save job | `savedJobsController`, `jobDetailController(id)` | Saved list updates; heart stays filled. |
| Unsave | `savedJobsController`, `jobDetailController(id)` | Saved list removes item; heart empties. |
| Sign-in success | `meController` (auto via authState listener) | Profile shows real name. |
| Sign-out | All `keepAlive: false` providers via authState listener | Read controllers reset. |

**We deliberately do not invalidate the feed on apply/save/withdraw/unsave.** The feed is "jobs that match you" — it doesn't reorder based on user activity, and refetching on every interaction would be wasteful and visually jarring. Applications and Saved tabs are the source of truth for "what I've done."

#### Mutation UX — optimistic vs server-roundtrip

| Mutation | Strategy | Rationale |
|---|---|---|
| Save / Unsave | **Optimistic** | Hearts and bookmarks textbook. Flip immediately; on error revert + snackbar. `POST /save` idempotent server-side. |
| Apply | **Server roundtrip** | Definitive before/after state ("Apply" → spinner → "Applied"); server-side side-effect chain (notification row inserted, future recruiter surfaces). Worth waiting for confirmation. |
| Withdraw | **Server roundtrip + confirmation dialog** | Destructive relative to applying. Confirmation is conventional. |
| Sign-out | **Server roundtrip** | Cheap, infrequent, user is leaving. |

Optimistic logic lives in the mutation controller, not the widget. `state` flips, then the fetch happens, then on error `ref.invalidate(savedJobsController)` rolls everything back to server truth.

#### Pagination contract

Feed, Applications, and Saved all paginate the same way (cursor in / cursor out). One reusable mixin is **premature** — the bodies are ~20 lines each, three identical-shaped controllers in v0 is acceptable. Revisit if a fourth list lands (rule of three).

### Primitive widgets

`presentation/widgets/` ships six:

- **`KpaLoadingView`** — centered `CircularProgressIndicator` with optional message.
- **`KpaErrorView`** — icon + headline + body + retry button. Headline/body derive from exception type.
- **`KpaEmptyState`** — illustration slot (svg or icon for v0) + headline + body + optional primary action.
- **`KpaScoreBadge`** — chip showing `total_score` as percent, color-graded by score band.
- **`KpaShellScaffold`** — wraps `StatefulShellRoute`'s body with the bottom nav. Tab config defined once here.
- **`AsyncValueWidget<T>`** — helper that collapses the AsyncValue three-way switch into a single call. Every screen renders one at its root.

`KpaCard`, `KpaListTile`, `KpaTextField` etc. are **not** built. Material 3 defaults themed with our tokens are fine for foundation.

### Theming + design tokens

Five token families in `presentation/theme/`:

- **`KpaColors`** — Material 3 `ColorScheme` slots backed by `kpaIndigo50…900` + `kpaNeutral50…900`. Separate semantic group for score-band colors (`scoreLow/Mid/High`).
- **`KpaTypography`** — Inter via `google_fonts` package; six size roles mapped onto Material 3's text theme.
- **`KpaSpacing`** — 4-base scale: `xs=4, sm=8, md=12, lg=16, xl=24, xxl=32, xxxl=48` as `const double`.
- **`KpaRadii`** — `sm=4, md=8, lg=12, xl=16, pill=999`.
- **`KpaMotion`** — re-exports Material defaults in v0; indirection lets us adjust globally later.

`ThemeData buildTheme(Brightness brightness)` is the single factory; light and dark constructed from the same primitives.

**v0 ships light only**, dark plumbed but disabled (`MaterialApp.router(themeMode: ThemeMode.light)`). Enabling dark later is `ThemeMode.system` + filling in dark-brightness values (~30 lines). Doing the plumbing now is the cheap option.

### Platform specifics

#### iOS — `app/ios/Runner/Info.plist`

```xml
<key>GIDClientID</key>
<string>$(GOOGLE_IOS_CLIENT_ID)</string>            <!-- xcconfig substitution -->
<key>CFBundleURLTypes</key>
<array>
  <dict>
    <key>CFBundleURLSchemes</key>
    <array><string>$(GOOGLE_IOS_REVERSED_CLIENT_ID)</string></array>
  </dict>
</array>
<key>NSAppTransportSecurity</key>
<dict><key>NSAllowsLocalNetworking</key><true/></dict>   <!-- debug-only convenience -->
```

Client IDs come from `Debug.xcconfig` / `Release.xcconfig` (gitignored; `*.xcconfig.example` committed).

#### Android — `app/android/app/src/main/AndroidManifest.xml`

No special manifest entries for Google Sign-In (plugin handles it). Debug-only additions:

```xml
<application
    android:usesCleartextTraffic="true"                       <!-- debug-only: lets emulator hit 10.0.2.2:8000 -->
    android:networkSecurityConfig="@xml/network_security_config">
```

`network_security_config.xml` whitelists `10.0.2.2` and `127.0.0.1` for debug builds; release uses a stricter config that forbids cleartext.

#### Web — `app/web/index.html`

Template variable substituted at build time:

```html
<meta name="google-signin-client_id" content="{{GOOGLE_WEB_CLIENT_ID}}">
```

Source committed as `web/index.template.html`; build script `app/scripts/build_web.sh` reads `--dart-define`d env vars, substitutes into a generated `web/index.html` (gitignored), then calls `flutter build web`.

### Build configuration

Three env vars at compile time via `String.fromEnvironment`, surfaced in `lib/core/config/env.dart`:

| Var | Purpose | Required |
|---|---|---|
| `KPA_API_BASE_URL` | Backend root (e.g., `http://localhost:8000`, `https://api.kpa-dev.example.com`) | yes |
| `KPA_GOOGLE_WEB_CLIENT_ID` | Google web client ID; used by web platform AND as `serverClientId` on mobile | yes |
| `KPA_BUILD_ENV` | `local` / `dev` / `prod` — affects logger verbosity + a "DEV" ribbon in non-prod builds | no (default `local`) |

**No build flavors in v0.** Flavors are right when you need per-environment app icons / bundle IDs / signing identities — none of which we need yet. `--dart-define` + GitHub Actions secrets is enough.

`env.dart` validates at app start; `runApp` is gated on it. Missing required env vars throw before any UI renders, with a printed message that explains the fix. Mirrors the backend's `Settings` boot-time validation.

### Pubspec — pinned packages

| Package | Role |
|---|---|
| `flutter_riverpod` + `riverpod_annotation` + `riverpod_generator` | State management |
| `freezed_annotation` + `freezed` + `json_annotation` + `json_serializable` | Models |
| `go_router` + `go_router_builder` | Routing |
| `dio` | HTTP client |
| `flutter_secure_storage` | Token storage |
| `google_sign_in` + `google_sign_in_web` | Auth |
| `google_fonts` | Inter for `KpaTypography` |
| `package_info_plus` | Version string on Profile |
| `intl` | Date formatting only — no localization |
| `very_good_analysis` | Lint rules (stricter than `flutter_lints`) |
| `build_runner` | Code-gen orchestration (dev only) |

Versions pinned at plan-write time. Notably absent: `dio_smart_retry`, `fluttertoast`, `cached_network_image`, any analytics SDK, Sentry/Crashlytics.

## Screens

### Splash — `/`

Built behind the platform native splash; user shouldn't perceive it in the happy path. Consumes `bootstrapControllerProvider`. Three terminal states:

- **Success** → router replaces with `/feed`. No visible UI flash.
- **No refresh token** → router replaces with `/signin`.
- **Network error during refresh** → `KpaErrorView` with retry. (4xx is not an error — it's a normal "needs sign-in" path.)

### Sign-in — `/signin`

Single screen, single CTA. Consumes `signInControllerProvider`. KPA wordmark + 1-line tagline (placeholder copy, not committed) + platform-correct Google Sign-In button:
- iOS / Android: `google_sign_in_button` from `google_sign_in` 6.x
- Web: GIS-rendered button via `HTMLElementView`

On press: button spinner during loading; success triggers router redirect via `authStateProvider`; failure renders inline error band + snackbar with underlying message.

No "continue as guest", no "sign up" — backend's `_upsert_identity` provisions the applicant row on first sign-in, so first-time and returning sign-in are the same flow.

### Feed — `/feed` (Tab 1)

Primary screen. Consumes `feedControllerProvider`. App bar with title "For you" + refresh icon (also pull-to-refresh). Body: `ListView.separated` of `FeedItemCard`s showing employer name, job title, location, posted-ago, `KpaScoreBadge` (`total_score`), and `explanation.fit` (one line, truncated). `explanation.caveat` renders as muted text below when present. Tapping pushes `/jobs/:id` onto the Feed tab's stack.

Pagination: scroll triggers `loadMore()` within 5 items of the end. Trailing slot: `KpaLoadingView` while `isLoadingMore`, "You're all caught up" string when `!hasMore`. Empty initial state: `KpaEmptyState` with "We're still looking for matches" + "Upload a resume to help us find you better roles."

ETag handling is invisible — dio caches the last response with its etag, revalidates on refresh; on `304` we keep existing state.

### Job detail — `/jobs/:id`

Pushed from any tab. Consumes `jobDetailControllerProvider(id)` returning `AsyncValue<JobDetail>` (`JobRead` + optional `MatchRead` + user's `Application` and `SavedJob` rows when present).

Body: employer header, title, location, posted-ago, **match explanation card** (`fit` + `caveat` paragraphs + "Why this match" subtitle + small generator label `templated` / future `LLM`), description paragraphs, sticky bottom action bar.

Action bar:
- **Apply / Withdraw** (primary)
- **Save / Saved** (heart, icon-only)

State table:
- `application=null` → "Apply" filled, taps → `applyController.submit()`.
- `application.status='applied'` → "Withdraw" outlined, taps → confirmation dialog → `withdrawController.submit()`.
- `application.status='withdrawn'` → "Apply" filled again (re-apply path).
- `savedJob=null` → heart outline, taps → optimistic flip + `saveController.submit()`.
- `savedJob` live → heart filled, taps → optimistic flip + `unsaveController.submit()`.

Mutation `AsyncValue` state is `ref.listen`-ed at screen level: errors become snackbars, successes are silent (UI reflects optimistically/declaratively). Uniform 404 from `/v1/jobs/:id` → `KpaEmptyState` with "This job is no longer available" + "Back to feed" button.

### Applications — `/applications` (Tab 3)

Consumes `applicationsControllerProvider`. List of cards: job title + employer + status pill (`Applied` / `Withdrawn`) + date. Tap → `/jobs/:id` (pushes onto Applications tab's stack — detail is shared across tabs via `StatefulShellRoute`'s per-tab stacks). Withdrawn applications kept visible (history). "Withdrawn 3 days ago" replaces "Applied 5 days ago" for those rows.

No swipe-to-withdraw — withdraw happens from detail behind a confirmation. Empty state: "No applications yet" + "Browse the feed" button that switches to tab 1.

### Saved — `/saved` (Tab 2)

Consumes `savedJobsControllerProvider`. Reuses `FeedItemCard` for visual consistency. Score badge hidden on closed jobs (`job.status != 'open'`); "Closed" pill replaces it. Tap → `/jobs/:id`. Swipe-to-unsave acceptable here (lightweight, reversible, user is curating); swipe reveals an unsave button rather than firing on swipe-end to prevent mis-touches. Empty state: "Nothing saved yet" + "Tap the heart on any job to save it for later."

### Profile — `/profile` (Tab 4)

Consumes `meControllerProvider`. Header: display name + email from `/v1/me`. "Account" subsection with placeholder rows for "Resume" (greyed "Coming soon") and "Notifications" (greyed "Coming soon") — signals that endpoints exist but UI is pending, prevents users from thinking the app is broken. **Sign out** button at bottom, visually separated. Confirmation dialog → `signOutController.submit()` → router redirect.

App version + build number rendered as muted small text at bottom via `package_info_plus`. Useful for bug reports.

### Cross-cutting screen behaviors

- **Auth-required redirect.** `go_router`'s `redirect` consults `authStateProvider`. Any route except `/` (splash) and `/signin` redirects to `/signin` when `SignedOut`. `/signin` redirects to `/feed` when `SignedIn`. Single rule, no per-screen auth check.
- **Deep links.** Only `/jobs/:id` is deep-linkable in v0. Opens directly when app launches with that URL (web) or via universal/app links (mobile, registered for `/jobs/:id` only). All other deep links fall through to `/feed`.
- **No back-stack across tabs.** Each tab keeps its own stack (`StatefulShellRoute.indexedStack`). Switching tabs does NOT pop. Tapping the active tab pops to the tab's root (iOS convention).

## Testing strategy

In priority order:

1. **Repository tests** (`test/unit/data/`). Mock dio; verify URL + method + headers + body construction; verify happy-path JSON parsing; verify each `problem+json` slug maps to the expected typed exception. The backend's slug list is captured here as the integration contract from the client side.

2. **Auth-refresh interceptor test** (`test/unit/data/api/refresh_interceptor_test.dart`). Most important test in the foundation. Cases:
   - 401 → single refresh → original replays → 200.
   - 401 → refresh returns 401 → original throws `AuthException`, `authStateProvider = SignedOut`, refresh token cleared.
   - Two concurrent 401s → exactly one refresh call (single-flight) → both originals replay with same new token.
   - Refresh during `skipAuth=true` request never attempted.
   - Network error during refresh → `NetworkException`, auth state unchanged.

3. **Provider tests** (`test/unit/presentation/`). Per AsyncNotifier: `ProviderContainer(overrides: [repoProvider.overrideWithValue(FakeRepo())])`, drive through state machine, assert `AsyncValue` transitions. Mutation controllers' invalidation behavior verified here.

4. **Widget smoke tests** (`test/widget/`). One file per screen. Three render cases: loading, success, error. No interaction depth — that's the integration test's job.

5. **Integration test** (`test/integration/golden_path_test.dart`). One end-to-end `testWidgets` run with Riverpod overrides + seeded fakes: launch → mock auth state `SignedIn` → assert feed renders → tap first card → assert detail renders → tap Apply → assert action bar flips to "Withdraw". No real network. ~150 lines.

**Deliberately skipped:**

- Visual regression / golden files (design not stable; maintenance heavy).
- Real-backend integration tests (`api/tests/integration/` covers contract; slug-level repo tests catch breakages).
- Platform-specific tests (matrix cost too high; manual smoke on three platforms before merge is the bar).
- Mutation testing, performance tests, accessibility audits (worth adding later; none worth blocking the foundation on).

## CI — `.github/workflows/app.yml`

New workflow, gated on `paths: app/**`. Single job, runs on PR + main:

```yaml
name: app
on:
  pull_request:
    paths: ['app/**']
  push:
    branches: [main]
    paths: ['app/**']

jobs:
  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: app
    steps:
      - uses: actions/checkout@v4
      - uses: subosito/flutter-action@v2
        with:
          channel: stable
          flutter-version: 3.27.x      # pinned; bumped explicitly
          cache: true
      - run: flutter pub get
      - run: dart run build_runner build --delete-conflicting-outputs
      - run: dart format --set-exit-if-changed lib test
      - run: flutter analyze
      - run: flutter test --coverage
```

Notes:
- No `flutter build web` step in v0 (5–10 min addition; failure modes usually platform-config drift caught faster locally).
- No backend workflow exists yet either; we don't block this on adding one.
- Codecov / coverage gates deferred until a meaningful baseline exists.
- Branch protection rules to require the `app` check are a user action (GitHub settings).

## Open follow-ups (not in scope)

Called out so they don't surprise anyone:

1. **Notifications inbox UI** — next natural slice. Endpoints exist; need a screen + unread-count surface.
2. **Resume upload UX** — file picker, camera capture, upload progress, parse-status polling.
3. **Deep link expansion** — `/applications/:id`, `/saved`, so push/email links land users directly.
4. **Recruiter app shape decision** — separate Flutter app, second Flutter app at `apps/recruiter/`, or a web-only React admin. Affects the directory-rename question we sidestepped.
5. **Telemetry + crash reporting** — Sentry vs Crashlytics; structured-log forwarding from the app to wherever Fluent Bit eventually points.
6. **Visual design pass** — replace placeholder tokens with real values once a designer enters the loop; add real illustrations to empty states.
7. **`flutter build web` in CI + a deploy target** — pairs with the backend's P5 deploy-target decision.
8. **Build flavors** — when per-env app icons / bundle IDs / signing identities become needed.
9. **Dark mode values** — flip `ThemeMode.system` + fill dark-brightness branch of `buildTheme`.
10. **Localization** — `flutter_intl` + .arb files when a second-language requirement lands.
