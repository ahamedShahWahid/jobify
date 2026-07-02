import 'dart:async';

import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_repository_impl.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'preferences_controller.g.dart';

@Riverpod(keepAlive: true)
class PreferencesController extends _$PreferencesController {
  @override
  Future<PreferencesDto> build() async =>
      ref.read(preferencesRepositoryProvider).fetch();

  Future<bool> submit(PreferencesUpdateDto update) async {
    // Preserve the loaded value across the submit: this provider is
    // keepAlive and shared (ProfileScreen, FeedNudgeBanner,
    // EditProfileScreen), so a bare AsyncLoading/AsyncError here would
    // radiate a data-less state to every watcher.
    final previous = state;
    // ignore: invalid_use_of_internal_member
    state = const AsyncValue<PreferencesDto>.loading().copyWithPrevious(
      previous,
    );
    final result = await AsyncValue.guard(
      () => ref.read(preferencesRepositoryProvider).update(update),
    );
    if (result.hasError) {
      final error =
          AsyncValue<PreferencesDto>.error(result.error!, result.stackTrace!);
      // ignore: invalid_use_of_internal_member
      state = error.copyWithPrevious(previous);
      return false;
    }
    state = AsyncValue.data(result.value!);
    return true;
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }
}
