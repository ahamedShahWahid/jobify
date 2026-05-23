import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/data/jobs/saved_jobs_repository_impl.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'saved_controller.g.dart';
part 'saved_controller.freezed.dart';

@freezed
abstract class SavedState with _$SavedState {
  const factory SavedState({
    required List<SavedJobListItemDto> items,
    required String? cursor,
    required bool hasMore,
    @Default(false) bool isLoadingMore,
  }) = _SavedState;
}

@riverpod
class SavedController extends _$SavedController {
  @override
  Future<SavedState> build() async {
    final repo = ref.read(savedJobsRepositoryProvider);
    final page = await repo.fetchPage();
    return SavedState(
      items: page.items,
      cursor: page.nextCursor,
      hasMore: page.nextCursor != null,
    );
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }

  Future<void> loadMore() async {
    final current = state.value;
    if (current == null || !current.hasMore || current.isLoadingMore) return;
    state = AsyncValue.data(current.copyWith(isLoadingMore: true));
    try {
      final repo = ref.read(savedJobsRepositoryProvider);
      final next = await repo.fetchPage(cursor: current.cursor);
      state = AsyncValue.data(
        SavedState(
          items: [...current.items, ...next.items],
          cursor: next.nextCursor,
          hasMore: next.nextCursor != null,
        ),
      );
    } catch (e, st) {
      // ignore: invalid_use_of_internal_member
      state = AsyncValue<SavedState>.error(e, st).copyWithPrevious(
        AsyncValue.data(current.copyWith(isLoadingMore: false)),
      );
    }
  }
}
