import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:kpa_app/data/jobs/applications_repository_impl.dart';
import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'applications_controller.g.dart';
part 'applications_controller.freezed.dart';

@freezed
abstract class ApplicationsState with _$ApplicationsState {
  const factory ApplicationsState({
    required List<ApplicationListItemDto> items,
    required String? cursor,
    required bool hasMore,
    @Default(false) bool isLoadingMore,
  }) = _ApplicationsState;
}

@riverpod
class ApplicationsController extends _$ApplicationsController {
  @override
  Future<ApplicationsState> build() async {
    final page = await ref
        .read(applicationsRepositoryProvider)
        .fetchPage();
    return ApplicationsState(
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
      final next = await ref
          .read(applicationsRepositoryProvider)
          .fetchPage(cursor: current.cursor);
      state = AsyncValue.data(
        ApplicationsState(
          items: [...current.items, ...next.items],
          cursor: next.nextCursor,
          hasMore: next.nextCursor != null,
        ),
      );
    } catch (e, st) {
      // ignore: invalid_use_of_internal_member
      state = AsyncValue<ApplicationsState>.error(e, st).copyWithPrevious(
        AsyncValue.data(current.copyWith(isLoadingMore: false)),
      );
    }
  }
}
