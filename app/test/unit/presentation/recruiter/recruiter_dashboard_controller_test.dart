import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/jobs/applicant_of_job_dto.dart';
import 'package:jobify_app/data/jobs/recruiter_job_dto.dart';
import 'package:jobify_app/data/jobs/recruiter_jobs_api.dart';
import 'package:jobify_app/data/jobs/recruiter_jobs_repository.dart';
import 'package:jobify_app/data/jobs/recruiter_jobs_repository_impl.dart';
import 'package:jobify_app/presentation/recruiter/recruiter_dashboard_controller.dart';

// Local fake — mirrors shape of recruiter_jobs_controller_test but only needs
// listMyJobs.
class _FakeRepo implements RecruiterJobsRepository {
  _FakeRepo(this._page);
  final RecruiterJobsPageDto _page;

  @override
  Future<RecruiterJobsPageDto> listMyJobs({
    String? status,
    String? cursor,
    int limit = 20,
  }) async =>
      _page;

  @override
  Future<RecruiterJobDto> createJob(Map<String, dynamic> body) async =>
      throw UnimplementedError();

  @override
  Future<RecruiterJobDto> patchJob(
    String id,
    Map<String, dynamic> body,
  ) async =>
      throw UnimplementedError();

  @override
  Future<void> deleteJob(String id) async => throw UnimplementedError();

  @override
  Future<ApplicantsOfJobPageDto> listApplicants(
    String jobId, {
    String? cursor,
    int limit = 20,
  }) async =>
      throw UnimplementedError();

  @override
  Future<ResumeDownload> downloadResume(String applicationId) async =>
      throw UnimplementedError();
}

RecruiterJobDto _job(
  String id, {
  String status = 'open',
  int applicantCount = 0,
  int surfacedMatchCount = 0,
}) =>
    RecruiterJobDto(
      id: id,
      title: 'Job $id',
      description: 'Desc',
      locations: const ['BLR'],
      minExpYears: 1,
      maxExpYears: 3,
      status: status,
      postedAt: DateTime.utc(2026),
      employerVerified: true,
      applicantCount: applicantCount,
      surfacedMatchCount: surfacedMatchCount,
    );

void main() {
  test('computes openJobs count correctly', () async {
    final items = [
      _job('j1'),
      _job('j2'),
      _job('j3', status: 'closed'),
    ];
    final container = ProviderContainer(
      overrides: [
        recruiterJobsRepositoryProvider.overrideWithValue(
          _FakeRepo(RecruiterJobsPageDto(items: items)),
        ),
      ],
    );
    addTearDown(container.dispose);

    final summary =
        await container.read(recruiterDashboardControllerProvider.future);
    expect(summary.openJobs, 2);
  });

  test('sums totalApplicants across all jobs', () async {
    final items = [
      _job('j1', applicantCount: 5),
      _job('j2', applicantCount: 3),
      _job('j3', applicantCount: 10),
    ];
    final container = ProviderContainer(
      overrides: [
        recruiterJobsRepositoryProvider.overrideWithValue(
          _FakeRepo(RecruiterJobsPageDto(items: items)),
        ),
      ],
    );
    addTearDown(container.dispose);

    final summary =
        await container.read(recruiterDashboardControllerProvider.future);
    expect(summary.totalApplicants, 18);
  });

  test('sums totalSurfacedMatches across all jobs', () async {
    final items = [
      _job('j1', surfacedMatchCount: 2),
      _job('j2', surfacedMatchCount: 7),
    ];
    final container = ProviderContainer(
      overrides: [
        recruiterJobsRepositoryProvider.overrideWithValue(
          _FakeRepo(RecruiterJobsPageDto(items: items)),
        ),
      ],
    );
    addTearDown(container.dispose);

    final summary =
        await container.read(recruiterDashboardControllerProvider.future);
    expect(summary.totalSurfacedMatches, 9);
  });

  test('recentJobs is capped at 5', () async {
    final items = List.generate(8, (i) => _job('j$i'));
    final container = ProviderContainer(
      overrides: [
        recruiterJobsRepositoryProvider.overrideWithValue(
          _FakeRepo(RecruiterJobsPageDto(items: items)),
        ),
      ],
    );
    addTearDown(container.dispose);

    final summary =
        await container.read(recruiterDashboardControllerProvider.future);
    expect(summary.recentJobs, hasLength(5));
  });

  test('recentJobs returns all items when fewer than 5', () async {
    final items = [_job('j1'), _job('j2')];
    final container = ProviderContainer(
      overrides: [
        recruiterJobsRepositoryProvider.overrideWithValue(
          _FakeRepo(RecruiterJobsPageDto(items: items)),
        ),
      ],
    );
    addTearDown(container.dispose);

    final summary =
        await container.read(recruiterDashboardControllerProvider.future);
    expect(summary.recentJobs, hasLength(2));
  });

  test('empty job list yields all-zero summary', () async {
    final container = ProviderContainer(
      overrides: [
        recruiterJobsRepositoryProvider.overrideWithValue(
          _FakeRepo(const RecruiterJobsPageDto(items: [])),
        ),
      ],
    );
    addTearDown(container.dispose);

    final summary =
        await container.read(recruiterDashboardControllerProvider.future);
    expect(summary.openJobs, 0);
    expect(summary.totalApplicants, 0);
    expect(summary.totalSurfacedMatches, 0);
    expect(summary.recentJobs, isEmpty);
  });
}
