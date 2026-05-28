import 'dart:async';

import 'package:kpa_app/data/resume/resume_dto.dart';
import 'package:kpa_app/data/resume/resume_repository_impl.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'resume_controller.g.dart';

@riverpod
class ResumeController extends _$ResumeController {
  @override
  Future<ResumeDto?> build() async =>
      ref.read(resumeRepositoryProvider).current();

  /// Upload picked file bytes. Returns true on success; the new (pending)
  /// resume becomes the state so the UI shows it immediately. The screen
  /// schedules follow-up refreshes to reflect the async parse result.
  Future<bool> uploadFromPicked({
    required List<int> bytes,
    required String filename,
    required String contentType,
  }) async {
    state = const AsyncValue.loading();
    final result = await AsyncValue.guard(
      () => ref.read(resumeRepositoryProvider).upload(
            bytes: bytes,
            filename: filename,
            contentType: contentType,
          ),
    );
    if (result.hasError) {
      state = AsyncValue.error(result.error!, result.stackTrace!);
      return false;
    }
    state = AsyncValue.data(result.value);
    return true;
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }
}
