import 'package:jobify_app/data/jobs/applicant_of_job_dto.dart';
import 'package:jobify_app/data/jobs/application_stage.dart';
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

  /// Optimistic stage change: patch the row locally, call the API, revert on
  /// error and rethrow so the screen can snackbar.
  Future<void> setStage(
    String applicationId,
    ApplicationStage stage,
  ) async {
    final prev = state;
    _patchRow(applicationId, stage);
    try {
      await ref
          .read(recruiterJobsRepositoryProvider)
          .setStage(jobId, applicationId, stage);
    } catch (_) {
      state = prev;
      rethrow;
    }
  }

  void _patchRow(String applicationId, ApplicationStage stage) {
    final current = state.value;
    if (current == null) return;
    state = AsyncValue.data(
      current.copyWith(
        items: [
          for (final row in current.items)
            if (row.applicationId == applicationId)
              ApplicantOfJobDto(
                applicationId: row.applicationId,
                applicantId: row.applicantId,
                displayName: row.displayName,
                email: row.email,
                status: row.status,
                stage: stage,
                appliedAt: row.appliedAt,
                matchScore: row.matchScore,
                matchExplanation: row.matchExplanation,
              )
            else
              row,
        ],
      ),
    );
  }
}
