import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/api/access_token_holder.dart';
import 'package:kpa_app/data/auth/auth_repository_impl.dart';
import 'package:kpa_app/data/auth/google_sign_in_data_source.dart';
import 'package:kpa_app/data/auth/token_storage.dart';
import 'package:kpa_app/data/auth/auth_state.dart';
import 'package:kpa_app/data/auth/user_role.dart';

import '../../../helpers/mock_interceptor.dart';

// ---------------------------------------------------------------------------
// Test doubles
// ---------------------------------------------------------------------------

class _InMemoryStorage implements TokenStorage {
  String? token;
  _InMemoryStorage([this.token]);

  @override
  Future<String?> readRefreshToken() async => token;

  @override
  Future<void> writeRefreshToken(String t) async => token = t;

  @override
  Future<void> clear() async => token = null;
}

class _FakeGoogle implements GoogleSignInDataSource {
  _FakeGoogle({this.idToken = 'GOOGLE_ID_TOKEN'});
  final String? idToken;

  @override
  Future<String> getIdToken() async {
    if (idToken == null) throw Exception('cancelled');
    return idToken!;
  }

  @override
  Future<void> signOut() async {}
}

// ---------------------------------------------------------------------------
// Harness builder
// ---------------------------------------------------------------------------

({
  AuthRepositoryImpl repo,
  AccessTokenHolder holder,
  _InMemoryStorage storage,
  MockInterceptor mock,
  List<AuthState> emitted,
}) _buildHarness({
  String? storedRefreshToken,
  String? googleIdToken = 'GOOGLE_ID_TOKEN',
}) {
  final holder = AccessTokenHolder();
  final storage = _InMemoryStorage(storedRefreshToken);
  final mock = MockInterceptor();
  final emitted = <AuthState>[];

  final dio = Dio(
    BaseOptions(
      baseUrl: 'http://test.local',
      validateStatus: (s) => s != null && s < 500,
    ),
  );
  dio.interceptors.add(mock);

  final repo = AuthRepositoryImpl(
    dio: dio,
    accessHolder: holder,
    tokenStorage: storage,
    google: _FakeGoogle(idToken: googleIdToken),
    emit: emitted.add,
    readState: () => emitted.isEmpty ? const SignedOut() : emitted.last,
  );

  return (
    repo: repo,
    holder: holder,
    storage: storage,
    mock: mock,
    emitted: emitted,
  );
}

// ---------------------------------------------------------------------------
// Helper response bodies
// ---------------------------------------------------------------------------

Map<String, dynamic> _signInBody({
  String access = 'ACCESS_TOKEN',
  String refresh = 'REFRESH_TOKEN',
  String userId = 'uid-1',
  String email = 'user@example.com',
  String? displayName = 'Test User',
}) =>
    {
      'access_token': access,
      'refresh_token': refresh,
      'user': {
        'id': userId,
        'email': email,
        'role': 'applicant',
        'display_name': displayName,
      },
    };

Map<String, dynamic> _refreshBody({
  String access = 'NEW_ACCESS',
  String refresh = 'NEW_REFRESH',
}) =>
    {
      'access_token': access,
      'refresh_token': refresh,
    };

Map<String, dynamic> _meBody({
  String userId = 'uid-1',
  String email = 'user@example.com',
  String? displayName = 'Test User',
}) =>
    {
      'id': userId,
      'email': email,
      'role': 'applicant',
      'display_name': displayName,
    };

Map<String, dynamic> _401Body() => {
      'type': 'about:blank',
      'title': 'Unauthorized',
      'status': 401,
      'slug': 'invalid_access_token',
      'detail': 'Token expired.',
    };

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  group('AuthRepositoryImpl', () {
    // 1. signInWithGoogle: 200 → SignedIn, holder set, storage written, emit.
    test('signInWithGoogle: 200 → returns SignedIn and persists tokens',
        () async {
      final h = _buildHarness();
      h.mock.on('POST', '/v1/auth/oauth/google', 200, _signInBody());

      final result = await h.repo.signInWithGoogle();

      expect(result.userId, 'uid-1');
      expect(result.email, 'user@example.com');
      expect(result.displayName, 'Test User');

      // Holder has access token.
      expect(h.holder.current, 'ACCESS_TOKEN');
      // Storage has refresh token.
      expect(await h.storage.readRefreshToken(), 'REFRESH_TOKEN');

      // Emitted: Authenticating → SignedIn.
      expect(h.emitted.length, 2);
      expect(h.emitted[0], isA<Authenticating>());
      expect(h.emitted[1], isA<SignedIn>());
      final emittedIn = h.emitted[1] as SignedIn;
      expect(emittedIn.userId, 'uid-1');
      expect(emittedIn.email, 'user@example.com');
    });

    // 1b. signInWithGoogle: role field is parsed from the OAuth exchange response.
    test('signInWithGoogle: role is parsed from the exchange response', () async {
      final h = _buildHarness();
      h.mock.on(
        'POST',
        '/v1/auth/oauth/google',
        200,
        _signInBody()
          ..['user'] = {
            'id': 'uid-1',
            'email': 'user@example.com',
            'role': 'recruiter',
            'display_name': 'Test User',
          },
      );

      final result = await h.repo.signInWithGoogle();

      expect(result.role, UserRole.recruiter);
    });

    // 2. signInWithGoogle: 401 → throws AuthException; emits SignedOut.
    test('signInWithGoogle: 401 → throws AuthException and emits SignedOut',
        () async {
      final h = _buildHarness();
      h.mock.on('POST', '/v1/auth/oauth/google', 401, _401Body());

      await expectLater(
        h.repo.signInWithGoogle(),
        throwsA(isA<Exception>()),
      );

      // Must have emitted Authenticating → SignedOut.
      expect(h.emitted.length, 2);
      expect(h.emitted[0], isA<Authenticating>());
      expect(h.emitted[1], isA<SignedOut>());
      // Holder must NOT have been set.
      expect(h.holder.current, isNull);
    });

    // 3. refreshSession: no stored token → throws AuthException no_refresh_token.
    test('refreshSession: no stored token → throws no_refresh_token', () async {
      final h = _buildHarness(storedRefreshToken: null);

      await expectLater(
        h.repo.refreshSession(),
        throwsA(
          isA<Exception>().having(
            (e) => e.toString(),
            'toString',
            contains('no_refresh_token'),
          ),
        ),
      );

      // Nothing should be emitted.
      expect(h.emitted, isEmpty);
    });

    // 4. refreshSession: 200 (refresh + /v1/me) → SignedIn hydrated.
    test('refreshSession: 200 → returns SignedIn with hydrated user', () async {
      final h = _buildHarness(storedRefreshToken: 'OLD_REFRESH');
      h.mock
        ..on('POST', '/v1/auth/refresh', 200, _refreshBody())
        ..on('GET', '/v1/me', 200, _meBody());

      final result = await h.repo.refreshSession();

      expect(result.userId, 'uid-1');
      expect(result.email, 'user@example.com');
      expect(result.displayName, 'Test User');

      // Holder updated.
      expect(h.holder.current, 'NEW_ACCESS');
      // Storage updated with new refresh token.
      expect(await h.storage.readRefreshToken(), 'NEW_REFRESH');

      // Request body must use the backend's `refresh_token` key (not `refresh`).
      final reqData = h.mock.lastDataFor('POST', '/v1/auth/refresh')
          as Map<String, dynamic>;
      expect(reqData['refresh_token'], 'OLD_REFRESH');

      // Emitted SignedIn.
      expect(h.emitted.length, 1);
      expect(h.emitted[0], isA<SignedIn>());
    });

    // 5. refreshSession: 401 from /v1/auth/refresh → clear + emit SignedOut + throws.
    test(
        'refreshSession: 401 from refresh endpoint → clears tokens and emits SignedOut',
        () async {
      final h = _buildHarness(storedRefreshToken: 'OLD_REFRESH');
      h.holder.set('OLD_ACCESS');
      h.mock.on('POST', '/v1/auth/refresh', 401, _401Body());

      await expectLater(
        h.repo.refreshSession(),
        throwsA(isA<Exception>()),
      );

      // Holder cleared.
      expect(h.holder.current, isNull);
      // Storage cleared.
      expect(await h.storage.readRefreshToken(), isNull);
      // Emitted SignedOut.
      expect(h.emitted.length, 1);
      expect(h.emitted[0], isA<SignedOut>());
    });

    // 6. signOut: clears everything even if /v1/auth/logout returns 500.
    test(
        'signOut: clears holder + storage + emits SignedOut even if logout fails',
        () async {
      final h = _buildHarness(storedRefreshToken: 'REFRESH');
      h.holder.set('ACCESS');
      // Server returns 500 — validateStatus covers < 500, so 500 will throw.
      // The impl wraps the logout in try/catch, so it must not propagate.
      h.mock.on('POST', '/v1/auth/logout', 500, {'error': 'server error'});

      await h.repo.signOut();

      // Holder cleared.
      expect(h.holder.current, isNull);
      // Storage cleared.
      expect(await h.storage.readRefreshToken(), isNull);
      // Emitted SignedOut.
      expect(h.emitted.length, 1);
      expect(h.emitted[0], isA<SignedOut>());
    });
  });
}
