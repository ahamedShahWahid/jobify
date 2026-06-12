/// Build-time environment configuration.
///
/// All values are sourced from `--dart-define` at compile time via
/// [String.fromEnvironment]. Unset vars come back as the empty string,
/// not null, so [collectMissing] tests for emptiness.
///
/// Call [validateOrThrow] from `main()` before `runApp` — a missing
/// required var should fail fast with a printable message.
abstract final class Env {
  static const apiBaseUrl = String.fromEnvironment('JOBIFY_API_BASE_URL');
  static const googleWebClientId =
      String.fromEnvironment('JOBIFY_GOOGLE_WEB_CLIENT_ID');
  static const buildEnv = String.fromEnvironment(
    'JOBIFY_BUILD_ENV',
    defaultValue: 'local',
  );

  static bool get isDev => buildEnv != 'prod';

  /// Validate the compiled-in values.
  /// Throws [StateError] if anything required is missing.
  static void validateOrThrow() {
    validateGiven(
      apiBaseUrl: apiBaseUrl,
      googleWebClientId: googleWebClientId,
    );
  }

  /// Internal helper, exposed for testing.
  /// Mirrors [validateOrThrow] but takes args.
  static void validateGiven({
    required String apiBaseUrl,
    required String googleWebClientId,
  }) {
    final missing = collectMissing(
      apiBaseUrl: apiBaseUrl,
      googleWebClientId: googleWebClientId,
    );
    if (missing.isEmpty) return;
    throw StateError(
      'Missing required --dart-define vars: ${missing.join(', ')}. '
      'Pass them on the flutter command line, e.g.:\n'
      '  flutter run --dart-define=JOBIFY_API_BASE_URL=http://localhost:8000 '
      '--dart-define=JOBIFY_GOOGLE_WEB_CLIENT_ID=<your-id>\n'
      'Or use --dart-define-from-file=.env (see app/.env.example).',
    );
  }

  /// Pure helper: returns the names of unset required vars.
  static List<String> collectMissing({
    required String apiBaseUrl,
    required String googleWebClientId,
  }) {
    return [
      if (apiBaseUrl.isEmpty) 'JOBIFY_API_BASE_URL',
      if (googleWebClientId.isEmpty) 'JOBIFY_GOOGLE_WEB_CLIENT_ID',
    ];
  }
}
