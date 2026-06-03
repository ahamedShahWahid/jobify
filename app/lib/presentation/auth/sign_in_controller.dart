import 'dart:async';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:kpa_app/data/auth/auth_repository_provider.dart';
import 'package:kpa_app/data/auth/google_web_sign_in.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'sign_in_controller.g.dart';

@riverpod
class SignInController extends _$SignInController {
  @override
  FutureOr<void> build() async {
    // Mobile uses the imperative [signInWithGoogle]. On web, Google's rendered
    // button drives sign-in: once the GIS client is initialized, subscribe to
    // its ID-token stream and complete the backend exchange when one arrives.
    if (kIsWeb) {
      final google = await ref.watch(googleWebSignInProvider.future);
      final sub = google.idTokens.listen(_completeWebSignIn);
      ref.onDispose(sub.cancel);
    }
  }

  Future<void> signInWithGoogle() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      await ref.read(authRepositoryProvider).signInWithGoogle();
    });
  }

  Future<void> _completeWebSignIn(String idToken) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      await ref.read(authRepositoryProvider).completeWebSignIn(idToken);
    });
  }
}
