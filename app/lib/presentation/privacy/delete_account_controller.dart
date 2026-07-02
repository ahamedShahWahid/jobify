import 'package:jobify_app/data/api/dio_provider.dart';
import 'package:jobify_app/data/auth/auth_state.dart';
import 'package:jobify_app/data/dsr/dsr_repository_impl.dart';
import 'package:jobify_app/presentation/auth/auth_providers.dart';
import 'package:jobify_app/presentation/auth/delete_success_snackbar_provider.dart';
import 'package:jobify_app/presentation/preferences/preferences_controller.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'delete_account_controller.g.dart';

@riverpod
class DeleteAccountController extends _$DeleteAccountController {
  @override
  AsyncValue<void> build() => const AsyncData(null);

  Future<void> submit() async {
    state = const AsyncLoading();
    try {
      await ref.read(dsrRepositoryProvider).deleteAccount();

      // Order matters: flag the snackbar BEFORE clearing the token so the
      // post-redirect render of /signin reads the flag.
      ref.read(deleteSuccessSnackbarProvider.notifier).fire();

      ref.read(accessTokenHolderProvider).clear();
      ref.read(authStateProvider.notifier).set(const SignedOut());
      // Same rationale as sign_out_controller.dart: the keepAlive
      // preferences cache must not leak the deleted user's data into the
      // next session.
      ref.invalidate(preferencesControllerProvider);

      state = const AsyncData(null);
    } catch (e, st) {
      state = AsyncError(e, st);
    }
  }
}
