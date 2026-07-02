import 'dart:async';

import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_repository_impl.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'preferences_controller.g.dart';

@riverpod
class PreferencesController extends _$PreferencesController {
  @override
  Future<PreferencesDto> build() async =>
      ref.read(preferencesRepositoryProvider).fetch();

  Future<bool> submit(PreferencesUpdateDto update) async {
    state = const AsyncValue.loading();
    final result = await AsyncValue.guard(
      () => ref.read(preferencesRepositoryProvider).update(update),
    );
    if (result.hasError) {
      state = AsyncValue.error(result.error!, result.stackTrace!);
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
