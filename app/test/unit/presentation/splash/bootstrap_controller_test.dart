import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/auth/auth_repository.dart';
import 'package:kpa_app/data/auth/auth_repository_provider.dart';
import 'package:kpa_app/data/auth/auth_state.dart';
import 'package:kpa_app/data/auth/user_role.dart';
import 'package:kpa_app/data/auth/token_storage.dart';
import 'package:kpa_app/presentation/splash/bootstrap_controller.dart';

class _FakeStorage implements TokenStorage {
  _FakeStorage([this.token]);
  String? token;
  @override
  Future<String?> readRefreshToken() async => token;
  @override
  Future<void> writeRefreshToken(String t) async => token = t;
  @override
  Future<void> clear() async => token = null;
}

class _FakeAuthRepo implements AuthRepository {
  _FakeAuthRepo({this.refreshThrows});
  Exception? refreshThrows;
  @override
  AuthState get current => const SignedOut();
  @override
  Future<SignedIn> signInWithGoogle() => throw UnimplementedError();
  @override
  Future<SignedIn> completeWebSignIn(String idToken) =>
      throw UnimplementedError();
  @override
  Future<SignedIn> refreshSession() async {
    if (refreshThrows != null) throw refreshThrows!;
    return const SignedIn(
        userId: 'u1', email: 'e@e.com', role: UserRole.applicant);
  }

  @override
  Future<String> refreshAccessTokenForInterceptor() =>
      throw UnimplementedError();
  @override
  Future<void> signOut() async {}
}

ProviderContainer _container({
  TokenStorage? storage,
  AuthRepository? repo,
}) {
  return ProviderContainer(
    overrides: [
      tokenStorageProvider.overrideWithValue(storage ?? _FakeStorage()),
      authRepositoryProvider.overrideWithValue(repo ?? _FakeAuthRepo()),
    ],
  );
}

void main() {
  test('no stored token → signIn', () async {
    final c = _container();
    final outcome = await c.read(bootstrapControllerProvider.future);
    expect(outcome, BootstrapOutcome.signIn);
  });

  test('stored token + refresh OK → feed', () async {
    final c = _container(storage: _FakeStorage('rt'));
    final outcome = await c.read(bootstrapControllerProvider.future);
    expect(outcome, BootstrapOutcome.feed);
  });

  test('stored token + refresh AuthException → signIn', () async {
    final c = _container(
      storage: _FakeStorage('rt'),
      repo: _FakeAuthRepo(
        refreshThrows: const AuthException(slug: 'invalid_refresh_token'),
      ),
    );
    final outcome = await c.read(bootstrapControllerProvider.future);
    expect(outcome, BootstrapOutcome.signIn);
  });

  // Note: error cases (NetworkException, ApiException(5xx)) are tested
  // indirectly via the integration tests in splash_screen_test.dart.
  // Direct unit testing of async error states in Riverpod async providers
  // has timing/disposal issues in the test harness; the widget test with
  // _StubError is the preferred approach.
}
