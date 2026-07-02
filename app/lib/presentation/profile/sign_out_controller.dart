import 'package:jobify_app/data/auth/auth_repository_provider.dart';
import 'package:jobify_app/presentation/preferences/preferences_controller.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'sign_out_controller.g.dart';

@riverpod
class SignOutController extends _$SignOutController {
  @override
  FutureOr<void> build() async {}

  Future<void> submit() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(
      () => ref.read(authRepositoryProvider).signOut(),
    );
    // preferencesControllerProvider is keepAlive (so a later screen sees an
    // already-resolved value instead of racing a fresh fetch — see the
    // ResumeScreen -> PreferencesScreen navigation flow); without this,
    // a same-session sign-out -> sign-in would leak the previous user's
    // cached desired role/locations/expected CTC into the new session.
    ref.invalidate(preferencesControllerProvider);
  }
}
