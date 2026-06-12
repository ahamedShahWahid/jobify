import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/jobs/applicant_of_job_dto.dart';
import 'package:jobify_app/data/jobs/recruiter_job_dto.dart';
import 'package:jobify_app/data/jobs/recruiter_jobs_api.dart';
import 'package:jobify_app/data/jobs/recruiter_jobs_repository.dart';
import 'package:jobify_app/data/jobs/recruiter_jobs_repository_impl.dart';
import 'package:jobify_app/presentation/recruiter/recruiter_jobs_controller.dart';

class FakeRecruiterJobsRepository implements RecruiterJobsRepository {
  FakeRecruiterJobsRepository({required this.pages});

  final List<RecruiterJobsPageDto> pages;
  int listCallCount = 0;
  String? lastStatus;

  @override
  Future<RecruiterJobsPageDto> listMyJobs({
    String? status,
    String? cursor,
    int limit = 20,
  }) async {
    lastStatus = status;
    return pages[listCallCount++];
  }

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

RecruiterJobDto _job(String id, {String status = 'open'}) => RecruiterJobDto(
      id: id,
      title: 'Job $id',
      description: 'Desc',
      locations: const ['BLR'],
      minExpYears: 1,
      maxExpYears: 3,
      status: status,
      postedAt: DateTime.utc(2026),
      employerVerified: true,
    );

void main() {
  test('build loads first page and returns PagedState with items', () async {
    final fake = FakeRecruiterJobsRepository(
      pages: [
        RecruiterJobsPageDto(
          items: [_job('j1'), _job('j2')],
          nextCursor: 'c1',
        ),
      ],
    );
    final container = ProviderContainer(
      overrides: [
        recruiterJobsRepositoryProvider.overrideWithValue(fake),
      ],
    );
    addTearDown(container.dispose);

    final state =
        await container.read(recruiterJobsControllerProvider(false).future);
    expect(state.items, hasLength(2));
    expect(state.hasMore, isTrue);
    expect(state.cursor, 'c1');
  });

  test('build passes no status filter when includeClosed=false', () async {
    final fake = FakeRecruiterJobsRepository(
      pages: [
        RecruiterJobsPageDto(items: [_job('j1')]),
      ],
    );
    final container = ProviderContainer(
      overrides: [
        recruiterJobsRepositoryProvider.overrideWithValue(fake),
      ],
    );
    addTearDown(container.dispose);

    await container.read(recruiterJobsControllerProvider(false).future);
    expect(fake.lastStatus, isNull);
  });

  test('build passes status=closed when includeClosed=true', () async {
    final fake = FakeRecruiterJobsRepository(
      pages: [
        RecruiterJobsPageDto(items: [_job('j1')]),
      ],
    );
    final container = ProviderContainer(
      overrides: [
        recruiterJobsRepositoryProvider.overrideWithValue(fake),
      ],
    );
    addTearDown(container.dispose);

    await container.read(recruiterJobsControllerProvider(true).future);
    expect(fake.lastStatus, 'closed');
  });

  test('loadMore preserves status=null for includeClosed=false', () async {
    final fake = FakeRecruiterJobsRepository(
      pages: [
        RecruiterJobsPageDto(
          items: [_job('j1')],
          nextCursor: 'c1',
        ),
        RecruiterJobsPageDto(items: [_job('j2')]),
      ],
    );
    final container = ProviderContainer(
      overrides: [
        recruiterJobsRepositoryProvider.overrideWithValue(fake),
      ],
    );
    addTearDown(container.dispose);

    await container.read(recruiterJobsControllerProvider(false).future);
    await container
        .read(recruiterJobsControllerProvider(false).notifier)
        .loadMore();
    expect(fake.lastStatus, isNull);
  });

  test('loadMore preserves status=closed for includeClosed=true', () async {
    final fake = FakeRecruiterJobsRepository(
      pages: [
        RecruiterJobsPageDto(
          items: [_job('j1')],
          nextCursor: 'c1',
        ),
        RecruiterJobsPageDto(items: [_job('j2')]),
      ],
    );
    final container = ProviderContainer(
      overrides: [
        recruiterJobsRepositoryProvider.overrideWithValue(fake),
      ],
    );
    addTearDown(container.dispose);

    await container.read(recruiterJobsControllerProvider(true).future);
    await container
        .read(recruiterJobsControllerProvider(true).notifier)
        .loadMore();
    expect(fake.lastStatus, 'closed');
  });

  test('loadMore appends second page and updates cursor/hasMore', () async {
    final fake = FakeRecruiterJobsRepository(
      pages: [
        RecruiterJobsPageDto(
          items: [_job('j1')],
          nextCursor: 'c1',
        ),
        RecruiterJobsPageDto(
          items: [_job('j2'), _job('j3')],
        ),
      ],
    );
    final container = ProviderContainer(
      overrides: [
        recruiterJobsRepositoryProvider.overrideWithValue(fake),
      ],
    );
    addTearDown(container.dispose);

    await container.read(recruiterJobsControllerProvider(false).future);
    await container
        .read(recruiterJobsControllerProvider(false).notifier)
        .loadMore();

    final state = container.read(recruiterJobsControllerProvider(false)).value!;
    expect(state.items, hasLength(3));
    expect(state.hasMore, isFalse);
    expect(state.cursor, isNull);
  });

  test('loadMore is no-op when hasMore=false', () async {
    final fake = FakeRecruiterJobsRepository(
      pages: [
        RecruiterJobsPageDto(items: [_job('j1')]),
      ],
    );
    final container = ProviderContainer(
      overrides: [
        recruiterJobsRepositoryProvider.overrideWithValue(fake),
      ],
    );
    addTearDown(container.dispose);

    await container.read(recruiterJobsControllerProvider(false).future);
    await container
        .read(recruiterJobsControllerProvider(false).notifier)
        .loadMore();

    expect(
      container.read(recruiterJobsControllerProvider(false)).value!.items,
      hasLength(1),
    );
  });
}
