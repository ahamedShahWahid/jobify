// ignore_for_file: directives_ordering
import 'package:dio/dio.dart';

import 'package:kpa_app/core/error/auth_slugs.dart';
import 'package:kpa_app/data/api/error_mapping.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/core/log/logger.dart';
import 'package:kpa_app/data/api/access_token_holder.dart';
import 'package:kpa_app/data/api/auth_header_interceptor.dart';
import 'package:kpa_app/data/auth/auth_dto.dart';
import 'package:kpa_app/data/auth/google_sign_in_data_source.dart';
import 'package:kpa_app/data/auth/token_storage.dart';
import 'package:kpa_app/data/auth/auth_repository.dart';
import 'package:kpa_app/data/me/me_dto.dart';
import 'package:kpa_app/data/auth/auth_state.dart';
import 'package:kpa_app/data/auth/user_role.dart';

class AuthRepositoryImpl implements AuthRepository {
  AuthRepositoryImpl({
    required Dio dio,
    required AccessTokenHolder accessHolder,
    required TokenStorage tokenStorage,
    required GoogleSignInDataSource google,
    required void Function(AuthState) emit,
    required AuthState Function() readState,
  })  : _dio = dio,
        _accessHolder = accessHolder,
        _tokenStorage = tokenStorage,
        _google = google,
        _emit = emit,
        _readState = readState;

  final Dio _dio;
  final AccessTokenHolder _accessHolder;
  final TokenStorage _tokenStorage;
  final GoogleSignInDataSource _google;
  final void Function(AuthState) _emit;
  final AuthState Function() _readState;
  final _log = KpaLogger.named('auth.repo');

  @override
  AuthState get current => _readState();

  void _push(AuthState s) {
    _emit(s);
  }

  @override
  Future<SignedIn> signInWithGoogle() async {
    _push(const Authenticating());
    final String idToken;
    try {
      idToken = await _google.getIdToken();
    } on AuthException {
      _push(const SignedOut());
      rethrow;
    }
    return _exchangeGoogleIdToken(idToken);
  }

  /// Web-only completion: the rendered Google button
  /// delivers the ID token asynchronously, so there's no imperative
  /// `getIdToken()` step — we go straight to the backend exchange.
  @override
  Future<SignedIn> completeWebSignIn(String idToken) async {
    _push(const Authenticating());
    return _exchangeGoogleIdToken(idToken);
  }

  /// Trade a Google ID token for a KPA session. Shared by the mobile imperative
  /// path and the web rendered-button path.
  Future<SignedIn> _exchangeGoogleIdToken(String idToken) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/v1/auth/oauth/google',
        data: {'id_token': idToken},
        options: Options(extra: {kSkipAuth: true}),
      );
      final dto = SignInResponseDto.fromJson(res.data!);
      _accessHolder.set(dto.access);
      await _tokenStorage.writeRefreshToken(dto.refresh);
      final signedIn = SignedIn(
        userId: dto.user.id,
        email: dto.user.email,
        role: UserRole.fromWire(dto.user.role),
        displayName: dto.user.displayName,
      );
      _push(signedIn);
      return signedIn;
    } on DioException catch (e) {
      _push(const SignedOut());
      throw mapDioException(e);
    }
  }

  @override
  Future<SignedIn> refreshSession() async {
    final stored = await _tokenStorage.readRefreshToken();
    if (stored == null) {
      throw const AuthException(
        slug: AuthSlugs.noRefreshToken,
        detail: 'Nothing to refresh.',
      );
    }
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/v1/auth/refresh',
        data: {'refresh_token': stored},
        options: Options(extra: {kSkipAuth: true}),
      );
      final dto = RefreshResponseDto.fromJson(res.data!);
      _accessHolder.set(dto.access);
      await _tokenStorage.writeRefreshToken(dto.refresh);
      final me = await _dio.get<Map<String, dynamic>>('/v1/me');
      final meDto = MeDto.fromJson(me.data!);
      final signedIn = SignedIn(
        userId: meDto.id,
        // AuthState.email is non-null display state; '' renders as "no email".
        email: meDto.email ?? '',
        role: UserRole.fromWire(meDto.role),
        displayName: meDto.displayName,
      );
      _push(signedIn);
      return signedIn;
    } on DioException catch (e) {
      _accessHolder.clear();
      await _tokenStorage.clear();
      _push(const SignedOut());
      throw mapDioException(e);
    }
  }

  /// Refresh callback used by the RefreshOn401Interceptor. Returns the new
  /// access token; the interceptor handles holder updates + replay.
  @override
  Future<String> refreshAccessTokenForInterceptor() async {
    final stored = await _tokenStorage.readRefreshToken();
    if (stored == null) {
      throw const AuthException(slug: AuthSlugs.noRefreshToken);
    }
    final res = await _dio.post<Map<String, dynamic>>(
      '/v1/auth/refresh',
      data: {'refresh_token': stored},
      options: Options(extra: {kSkipAuth: true}),
    );
    final dto = RefreshResponseDto.fromJson(res.data!);
    await _tokenStorage.writeRefreshToken(dto.refresh);
    return dto.access;
  }

  @override
  Future<void> signOut() async {
    try {
      // Backend LogoutRequest requires refresh_token to revoke the family
      // server-side; without it the token family is never invalidated.
      final stored = await _tokenStorage.readRefreshToken();
      if (stored != null) {
        await _dio.post<dynamic>(
          '/v1/auth/logout',
          data: {'refresh_token': stored},
        );
      }
    } catch (e, s) {
      _log.warn('logout request failed (continuing)', error: e, stack: s);
    }
    await _google.signOut();
    _accessHolder.clear();
    await _tokenStorage.clear();
    _push(const SignedOut());
  }
}
