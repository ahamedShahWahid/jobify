// ignore_for_file: directives_ordering
import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'package:kpa_app/core/config/env.dart';
import 'package:kpa_app/data/api/access_token_holder.dart';
import 'package:kpa_app/data/api/auth_header_interceptor.dart';
import 'package:kpa_app/data/api/request_id_interceptor.dart';

part 'dio_provider.g.dart';

@Riverpod(keepAlive: true)
AccessTokenHolder accessTokenHolder(Ref ref) => AccessTokenHolder();

@Riverpod(keepAlive: true)
Dio dio(Ref ref) {
  final holder = ref.read(accessTokenHolderProvider);
  final dio = Dio(
    BaseOptions(
      // ignore: avoid_redundant_argument_values
      baseUrl: Env.apiBaseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 30),
      validateStatus: (s) => s != null && s < 500,
    ),
  );
  dio.interceptors.add(RequestIdInterceptor());
  dio.interceptors.add(AuthHeaderInterceptor(holder));
  // RefreshOn401Interceptor is added in Task 13 (after AuthRepository exists).
  return dio;
}
