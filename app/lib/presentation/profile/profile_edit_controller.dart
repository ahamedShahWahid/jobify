import 'dart:async';

import 'package:jobify_app/data/me/me_repository_impl.dart';
import 'package:jobify_app/data/me/profile_update_dto.dart';
import 'package:jobify_app/presentation/profile/me_controller.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'profile_edit_controller.g.dart';

@riverpod
class ProfileEditController extends _$ProfileEditController {
  @override
  FutureOr<void> build() {}

  /// Submit the edit. Returns true on success (and invalidates the cached me),
  /// false on error (state carries the error for the UI to surface).
  Future<bool> submit(ProfileUpdateDto update) async {
    state = const AsyncValue.loading();
    final result = await AsyncValue.guard(
      () => ref.read(meRepositoryProvider).updateProfile(update),
    );
    if (result.hasError) {
      state = AsyncValue.error(result.error!, result.stackTrace!);
      return false;
    }
    state = const AsyncValue.data(null);
    ref.invalidate(meControllerProvider);
    return true;
  }
}
