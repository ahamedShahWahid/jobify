import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:jobify_app/data/jobs/saved_jobs_repository_impl.dart';
import 'package:jobify_app/presentation/paging/paged_state.dart';
import 'package:jobify_app/presentation/paging/paging.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'saved_controller.g.dart';

typedef SavedState = PagedState<SavedJobListItemDto>;

@riverpod
class SavedController extends _$SavedController {
  @override
  Future<SavedState> build() async {
    final repo = ref.read(savedJobsRepositoryProvider);
    final page = await repo.fetchPage();
    return PagedState(
      items: page.items,
      cursor: page.nextCursor,
      hasMore: page.nextCursor != null,
    );
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }

  Future<void> loadMore() => loadNextPage<SavedJobListItemDto>(
        currentState: state,
        fetch: ({String? cursor}) async {
          final page = await ref
              .read(savedJobsRepositoryProvider)
              .fetchPage(cursor: cursor);
          return PagedState(
            items: page.items,
            cursor: page.nextCursor,
            hasMore: page.nextCursor != null,
          );
        },
        setState: (s) => state = s,
      );
}
