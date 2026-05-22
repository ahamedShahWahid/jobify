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

# Web
sed "s|{{GOOGLE_WEB_CLIENT_ID}}|$KPA_GOOGLE_WEB_CLIENT_ID|g" \
  web/index.template.html > web/index.html
flutter run -d chrome --dart-define-from-file=.env
```

Note Android needs `http://10.0.2.2:8000` (emulator's host loopback alias) instead of `localhost`.

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

Pragmatic Clean Architecture — `lib/data/` + `lib/domain/` + `lib/presentation/` + `lib/core/`. Repository interfaces live in `domain/`; impls in `data/`; Riverpod providers + screens in `presentation/`. Cross-layer infrastructure (env validation, typed exceptions, logger) in `core/`.

See `docs/superpowers/specs/2026-05-21-flutter-app-shell-design.md` for the design doc.
