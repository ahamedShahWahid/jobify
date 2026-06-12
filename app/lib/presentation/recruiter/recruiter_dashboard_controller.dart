import 'package:jobify_app/data/jobs/recruiter_job_dto.dart';
import 'package:jobify_app/data/jobs/recruiter_jobs_repository_impl.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'recruiter_dashboard_controller.g.dart';

class RecruiterDashboardSummary {
  const RecruiterDashboardSummary({
    required this.openJobs,
    required this.totalApplicants,
    required this.totalSurfacedMatches,
    required this.recentJobs,
  });

  final int openJobs;
  final int totalApplicants;
  final int totalSurfacedMatches;
  final List<RecruiterJobDto> recentJobs;
}

@riverpod
class RecruiterDashboardController extends _$RecruiterDashboardController {
  @override
  Future<RecruiterDashboardSummary> build() async {
    // status: 'closed' returns BOTH open and closed jobs (backend semantics),
    // so openJobs counts correctly and the totals include closed-job counts.
    // MVP-documented approximation for recruiters with >100 jobs (one page).
    final page = await ref
        .read(recruiterJobsRepositoryProvider)
        .listMyJobs(status: 'closed', limit: 100);
    final items = page.items;
    return RecruiterDashboardSummary(
      openJobs: items.where((j) => j.status == 'open').length,
      totalApplicants: items.fold(0, (sum, j) => sum + j.applicantCount),
      totalSurfacedMatches:
          items.fold(0, (sum, j) => sum + j.surfacedMatchCount),
      recentJobs: items.take(5).toList(),
    );
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }
}
