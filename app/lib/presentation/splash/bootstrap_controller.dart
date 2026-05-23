import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/auth/auth_repository_impl.dart';
import 'package:kpa_app/data/auth/token_storage.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'bootstrap_controller.g.dart';

enum BootstrapOutcome { feed, signIn }

@riverpod
class BootstrapController extends _$BootstrapController {
  @override
  Future<BootstrapOutcome> build() async {
    final storage = ref.read(tokenStorageProvider);
    final token = await storage.readRefreshToken();
    if (token == null) return BootstrapOutcome.signIn;

    final repo = ref.read(authRepositoryProvider);
    try {
      await repo.refreshSession();
      return BootstrapOutcome.feed;
    } on AuthException {
      // 4xx from refresh: needs sign-in (not an error)
      return BootstrapOutcome.signIn;
    }
    // NetworkException / ApiException(5xx) bubble → AsyncValue.error → retry UI.
  }

  Future<void> retry() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(build);
  }
}
