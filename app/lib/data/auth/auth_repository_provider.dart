// ignore_for_file: directives_ordering
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/data/api/dio_provider.dart';
import 'package:kpa_app/data/auth/auth_repository.dart';
import 'package:kpa_app/data/auth/auth_repository_impl.dart';
import 'package:kpa_app/data/auth/google_sign_in_data_source.dart';
import 'package:kpa_app/data/auth/token_storage.dart';
import 'package:kpa_app/presentation/auth/auth_providers.dart';

part 'auth_repository_provider.g.dart';

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
