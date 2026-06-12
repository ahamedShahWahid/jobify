import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/core/config/env.dart';

void main() {
  group('Env', () {
    test('exposes the four documented getters', () {
      // We can't really test --dart-define behavior in a unit test without
      // spawning a subprocess. This test is a structural smoke test that the
      // getters exist and return strings.
      expect(Env.apiBaseUrl, isA<String>());
      expect(Env.googleWebClientId, isA<String>());
      expect(Env.buildEnv, isA<String>());
      expect(Env.isDev, isA<bool>());
    });

    test('validateOrThrow lists every missing required var in one message', () {
      // We can't drive --dart-define from a test, so we test the helper
      // directly with explicit args.
      final missing = Env.collectMissing(
        apiBaseUrl: '',
        googleWebClientId: '',
      );
      expect(missing,
          equals(['JOBIFY_API_BASE_URL', 'JOBIFY_GOOGLE_WEB_CLIENT_ID']));
    });

    test('collectMissing returns empty when everything set', () {
      final missing = Env.collectMissing(
        apiBaseUrl: 'http://localhost:8000',
        googleWebClientId: 'abc.apps.googleusercontent.com',
      );
      expect(missing, isEmpty);
    });

    test('validateOrThrow throws with all missing vars and a fix hint', () {
      expect(
        () => Env.validateGiven(apiBaseUrl: '', googleWebClientId: ''),
        throwsA(
          isA<StateError>().having(
            (e) => e.message,
            'message',
            allOf(
              contains('JOBIFY_API_BASE_URL'),
              contains('JOBIFY_GOOGLE_WEB_CLIENT_ID'),
              contains('--dart-define'),
            ),
          ),
        ),
      );
    });
  });
}
