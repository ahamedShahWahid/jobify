import 'package:jobify_app/data/jobs/applicant_of_job_dto.dart';
import 'package:jobify_app/data/jobs/recruiter_jobs_repository_impl.dart';
import 'package:jobify_app/presentation/paging/paged_state.dart';
import 'package:jobify_app/presentation/paging/paging.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'recruiter_applicants_controller.g.dart';

typedef RecruiterApplicantsState = PagedState<ApplicantOfJobDto>;

@riverpod
class RecruiterApplicantsController extends _$RecruiterApplicantsController {
  @override
  Future<RecruiterApplicantsState> build(String jobId) async {
    final page =
        await ref.read(recruiterJobsRepositoryProvider).listApplicants(jobId);
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

  Future<void> loadMore() => loadNextPage<ApplicantOfJobDto>(
        currentState: state,
        fetch: ({String? cursor}) async {
          final page = await ref
              .read(recruiterJobsRepositoryProvider)
              .listApplicants(jobId, cursor: cursor);
          return PagedState(
            items: page.items,
            cursor: page.nextCursor,
            hasMore: page.nextCursor != null,
          );
        },
        setState: (s) => state = s,
      );
}
