import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:jobify_app/core/config/env.dart';
import 'package:jobify_app/data/api/access_token_holder.dart';
import 'package:jobify_app/data/api/auth_header_interceptor.dart';
import 'package:jobify_app/data/api/refresh_on_401_interceptor.dart';
import 'package:jobify_app/data/api/request_id_interceptor.dart';
import 'package:jobify_app/data/auth/auth_repository.dart';
import 'package:jobify_app/data/auth/auth_repository_impl.dart';
import 'package:jobify_app/data/auth/auth_state.dart';
import 'package:jobify_app/data/auth/google_sign_in_data_source.dart';
import 'package:jobify_app/data/auth/token_storage.dart';
import 'package:jobify_app/presentation/auth/auth_providers.dart';

/// Runtime services whose construction has mutual callback requirements.
///
/// Keeping this wiring in the application composition root prevents data-layer
/// provider modules from importing each other (Dio -> auth repository -> Dio).
final class AppServices {
  const AppServices({
    required this.dio,
    required this.authRepository,
    required this.accessTokenHolder,
  });

  final Dio dio;
  final AuthRepository authRepository;
  final AccessTokenHolder accessTokenHolder;
}

final appServicesProvider = Provider<AppServices>((ref) {
  final holder = AccessTokenHolder();
  final dio = Dio(
    BaseOptions(
      // ignore: avoid_redundant_argument_values
      baseUrl: Env.apiBaseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 30),
    ),
  );

  late final AuthRepository repository;
  repository = AuthRepositoryImpl(
    dio: dio,
    accessHolder: holder,
    tokenStorage: ref.read(tokenStorageProvider),
    google: GoogleSignInDataSourceImpl(),
    emit: (state) => ref.read(authStateProvider.notifier).set(state),
    readState: () => ref.read(authStateProvider),
  );

  dio.interceptors.add(RequestIdInterceptor());
  dio.interceptors.add(AuthHeaderInterceptor(holder));
  dio.interceptors.add(
    RefreshOn401Interceptor(
      holder: holder,
      dio: dio,
      refresh: repository.refreshAccessTokenForInterceptor,
      onSignedOut: () {
        ref.read(authStateProvider.notifier).set(const SignedOut());
      },
    ),
  );

  ref.onDispose(dio.close);
  return AppServices(
    dio: dio,
    authRepository: repository,
    accessTokenHolder: holder,
  );
});

final accessTokenHolderProvider = Provider<AccessTokenHolder>(
  (ref) => ref.watch(appServicesProvider).accessTokenHolder,
);

final dioProvider = Provider<Dio>(
  (ref) => ref.watch(appServicesProvider).dio,
);

final authRepositoryProvider = Provider<AuthRepository>(
  (ref) => ref.watch(appServicesProvider).authRepository,
);
