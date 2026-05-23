// ignore_for_file: directives_ordering
import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/api/error_mapping.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/core/log/logger.dart';
import 'package:kpa_app/data/api/access_token_holder.dart';
import 'package:kpa_app/data/api/auth_header_interceptor.dart';
import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/data/auth/auth_dto.dart';
import 'package:kpa_app/data/auth/google_sign_in_data_source.dart';
import 'package:kpa_app/data/auth/token_storage.dart';
import 'package:kpa_app/domain/auth/auth_repository.dart';
import 'package:kpa_app/domain/auth/auth_state.dart';
import 'package:kpa_app/presentation/auth/auth_providers.dart';

part 'auth_repository_impl.g.dart';

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
    try {
      final idToken = await _google.getIdToken();
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
        displayName: dto.user.displayName,
      );
      _push(signedIn);
      return signedIn;
    } on DioException catch (e) {
      _push(const SignedOut());
      throw mapDioException(e);
    } on AuthException {
      _push(const SignedOut());
      rethrow;
    }
  }

  @override
  Future<SignedIn> refreshSession() async {
    final stored = await _tokenStorage.readRefreshToken();
    if (stored == null) {
      throw const AuthException(
        slug: 'no_refresh_token',
        detail: 'Nothing to refresh.',
      );
    }
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/v1/auth/refresh',
        data: {'refresh': stored},
        options: Options(extra: {kSkipAuth: true}),
      );
      final dto = RefreshResponseDto.fromJson(res.data!);
      _accessHolder.set(dto.access);
      await _tokenStorage.writeRefreshToken(dto.refresh);
      final me = await _dio.get<Map<String, dynamic>>('/v1/me');
      final user = me.data!['user'] as Map<String, dynamic>;
      final signedIn = SignedIn(
        userId: user['id'] as String,
        email: user['email'] as String,
        displayName: user['display_name'] as String?,
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
  Future<String> refreshAccessTokenForInterceptor() async {
    final stored = await _tokenStorage.readRefreshToken();
    if (stored == null) {
      throw const AuthException(slug: 'no_refresh_token');
    }
    final res = await _dio.post<Map<String, dynamic>>(
      '/v1/auth/refresh',
      data: {'refresh': stored},
      options: Options(extra: {kSkipAuth: true}),
    );
    final dto = RefreshResponseDto.fromJson(res.data!);
    await _tokenStorage.writeRefreshToken(dto.refresh);
    return dto.access;
  }

  @override
  Future<void> signOut() async {
    try {
      await _dio.post<dynamic>('/v1/auth/logout');
    } catch (e, s) {
      _log.warn('logout request failed (continuing)', error: e, stack: s);
    }
    await _google.signOut();
    _accessHolder.clear();
    await _tokenStorage.clear();
    _push(const SignedOut());
  }
}

@Riverpod(keepAlive: true)
AuthRepository authRepository(Ref ref) {
  return AuthRepositoryImpl(
    dio: ref.read(dioProvider),
    accessHolder: ref.read(accessTokenHolderProvider),
    tokenStorage: ref.read(tokenStorageProvider),
    google: GoogleSignInDataSourceImpl(),
    emit: (s) => ref.read(authStateProvider.notifier).set(s),
    readState: () => ref.read(authStateProvider),
  );
}
