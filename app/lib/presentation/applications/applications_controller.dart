import 'package:jobify_app/data/jobs/applications_repository_impl.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:jobify_app/presentation/paging/paged_state.dart';
import 'package:jobify_app/presentation/paging/paging.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'applications_controller.g.dart';

typedef ApplicationsState = PagedState<ApplicationListItemDto>;

@riverpod
class ApplicationsController extends _$ApplicationsController {
  @override
  Future<ApplicationsState> build() async {
    final page = await ref.read(applicationsRepositoryProvider).fetchPage();
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

  Future<void> loadMore() => loadNextPage<ApplicationListItemDto>(
        currentState: state,
        fetch: ({String? cursor}) async {
          final page = await ref
              .read(applicationsRepositoryProvider)
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
