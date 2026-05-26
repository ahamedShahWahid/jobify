# KPA — Flutter app

iOS + Android + Web client for the KPA platform. Built on the foundation laid out in `docs/superpowers/specs/2026-05-21-flutter-app-shell-design.md`.

## Stack

- Flutter 3.27.x (stable channel)
- Riverpod 4.x (upgraded from spec's 2.x to unblock build_runner)
- freezed 3.x, dio 5.7, go_router 14.6
- google_sign_in 6.2 + google_sign_in_web 0.12 for auth
- flutter_secure_storage 9.2 for refresh-token persistence

## First-time setup

```bash
cd app
flutter pub get
dart run build_runner build --delete-conflicting-outputs
```

Copy `.env.example` → `.env` and fill in `KPA_GOOGLE_WEB_CLIENT_ID` + `KPA_API_BASE_URL` (defaults work for local dev against `http://localhost:8000`).

### iOS one-time setup

Open `ios/Runner.xcworkspace` in Xcode. Select the `Runner` project, then under *Info → Configurations*, set:

- Debug config file → `Runner/Debug.xcconfig`
- Release config file → `Runner/Release.xcconfig`

Copy `ios/Runner/Debug.xcconfig.example` → `ios/Runner/Debug.xcconfig` (gitignored) and fill in real values from Google Cloud Console.

## Run

The backend must be running on `http://localhost:8000` first (see `api/README.md`).

```bash
# iOS simulator
flutter run -d ios --dart-define-from-file=.env

# Android emulator
flutter run -d emulator-5554 \
  --dart-define=KPA_API_BASE_URL=http://10.0.2.2:8000 \
  --dart-define-from-file=.env

# Web — pin the port so it matches the Google OAuth allowlist (see below)
flutter run -d web-server --web-port=8080 --dart-define-from-file=.env
# (or `-d chrome` for a live browser, but it picks a random port that won't
#  match Authorized JavaScript origins — prefer the pinned web-server port)
```

Note Android needs `http://10.0.2.2:8000` (emulator's host loopback alias) instead of `localhost`.

### Web Google sign-in (extra setup)

Web auth is a different flow from mobile: Google Identity Services only returns an
ID token via its **rendered button**, so on web the app shows Google's "Sign in with
Google" button (mobile keeps the in-app `FilledButton`). Two things must be configured
or the button 403s / sign-in fails:

1. **Authorized JavaScript origins** — in Google Cloud → APIs & Services → Credentials,
   open the **Web** OAuth client and add the exact dev origin (`http://localhost:8080`,
   no trailing slash) under *Authorized JavaScript origins* (NOT redirect URIs). Changes
   take 5 min – a few hours to propagate. Probe readiness without a browser:
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' -H 'Origin: http://localhost:8080' \
     'https://accounts.google.com/gsi/button?client_id=<WEB_CLIENT_ID>&is_fedcm_supported=true'
   # 403 = origin not allowed yet; 200 = live
   ```
2. **API CORS** — the backend must allowlist the web origin. `KPA_CORS_ALLOW_ORIGINS`
   (default `http://localhost:8080`) drives the API's CORS middleware. See `api/README.md`.

The `clientId` is passed to `GoogleSignIn` directly via `--dart-define`, so the
`web/index.template.html` → `web/index.html` `sed` step is no longer needed for auth.

## Test

```bash
flutter test                       # all tests
flutter test test/unit/            # unit only
flutter test test/widget/          # widget only
flutter test test/integration/     # the golden-path integration test
```

## Lint + format

```bash
dart format lib test
flutter analyze
```

CI (`.github/workflows/app.yml`) enforces both on every PR touching `app/**`.

## Architecture

`lib/data/` + `lib/presentation/` + `lib/core/` (no separate `domain/` layer). Abstract repository interfaces live next to their concrete impls in `data/<feature>/<repo>_repository.dart` + `<repo>_repository_impl.dart`. Riverpod providers + screens in `presentation/`. Cross-layer infrastructure (env validation, typed exceptions, logger) in `core/`.

See `docs/superpowers/specs/2026-05-21-flutter-app-shell-design.md` for the design doc.
