import 'package:kpa_app/data/jobs/recruiter_job_dto.dart';
import 'package:kpa_app/data/jobs/recruiter_jobs_repository_impl.dart';
import 'package:kpa_app/presentation/paging/paged_state.dart';
import 'package:kpa_app/presentation/paging/paging.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'recruiter_jobs_controller.g.dart';

typedef RecruiterJobsState = PagedState<RecruiterJobDto>;

@riverpod
class RecruiterJobsController extends _$RecruiterJobsController {
  @override
  Future<RecruiterJobsState> build(bool includeClosed) async {
    final page = await ref.read(recruiterJobsRepositoryProvider).listMyJobs(
          status: includeClosed ? null : 'open',
        );
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

  Future<void> loadMore() => loadNextPage<RecruiterJobDto>(
        currentState: state,
        fetch: ({String? cursor}) async {
          final page = await ref
              .read(recruiterJobsRepositoryProvider)
              .listMyJobs(
                status: includeClosed ? null : 'open',
                cursor: cursor,
              );
          return PagedState(
            items: page.items,
            cursor: page.nextCursor,
            hasMore: page.nextCursor != null,
          );
        },
        setState: (s) => state = s,
      );
}
