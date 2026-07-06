import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/jobs/application_source.dart';
import 'package:jobify_app/data/jobs/application_status.dart';
import 'package:jobify_app/data/jobs/applications_repository.dart';
import 'package:jobify_app/data/jobs/applications_repository_impl.dart';
import 'package:jobify_app/data/jobs/job_status.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:jobify_app/data/jobs/saved_jobs_repository.dart';
import 'package:jobify_app/data/jobs/saved_jobs_repository_impl.dart';
import 'package:jobify_app/presentation/feed/feed_summary_controller.dart';

class _FakeApplicationsRepo implements ApplicationsRepository {
  _FakeApplicationsRepo(this._page);
  final ApplicationsPageDto _page;

  @override
  Future<ApplicationsPageDto> fetchPage({
    String? cursor,
    int limit = 20,
  }) async =>
      _page;

  @override
  Future<ApplicationDto> withdraw(String applicationId) async =>
      throw UnimplementedError();
}

class _FakeSavedJobsRepo implements SavedJobsRepository {
  _FakeSavedJobsRepo(this._page);
  final SavedJobsPageDto _page;

  @override
  Future<SavedJobsPageDto> fetchPage({String? cursor, int limit = 20}) async =>
      _page;
}

final _job = JobSummaryDto(
  id: 'j1',
  title: 'Engineer',
  locations: const ['BLR'],
  status: JobStatus.open,
  postedAt: DateTime.parse('2026-05-18T00:00:00Z'),
);
const _employer = EmployerSummaryDto(id: 'e1', name: 'Acme Co');

ApplicationListItemDto _application(String id) => ApplicationListItemDto(
      application: ApplicationDto(
        id: id,
        jobId: 'j1',
        status: ApplicationStatus.applied,
        source: ApplicationSource.feed,
        createdAt: DateTime.parse('2026-05-18T00:00:00Z'),
        updatedAt: DateTime.parse('2026-05-18T00:00:00Z'),
      ),
      job: _job,
      employer: _employer,
    );

SavedJobListItemDto _saved(String id) => SavedJobListItemDto(
      saved: SavedJobDto(
        id: id,
        jobId: 'j1',
        createdAt: DateTime.parse('2026-05-18T00:00:00Z'),
      ),
      job: _job,
      employer: _employer,
    );

void main() {
  test('counts items and reports no approximation when nextCursor is null',
      () async {
    final container = ProviderContainer(
      overrides: [
        applicationsRepositoryProvider.overrideWithValue(
          _FakeApplicationsRepo(
            ApplicationsPageDto(
              items: [_application('a1'), _application('a2')],
            ),
          ),
        ),
        savedJobsRepositoryProvider.overrideWithValue(
          _FakeSavedJobsRepo(SavedJobsPageDto(items: [_saved('s1')])),
        ),
      ],
    );
    addTearDown(container.dispose);

    final summary = await container.read(feedSummaryControllerProvider.future);
    expect(summary.applicationsCount, 2);
    expect(summary.applicationsApprox, isFalse);
    expect(summary.savedCount, 1);
    expect(summary.savedApprox, isFalse);
  });

  test('reports approximation when nextCursor is present', () async {
    final container = ProviderContainer(
      overrides: [
        applicationsRepositoryProvider.overrideWithValue(
          _FakeApplicationsRepo(
            ApplicationsPageDto(
              items: [_application('a1')],
              nextCursor: 'cursor-1',
            ),
          ),
        ),
        savedJobsRepositoryProvider.overrideWithValue(
          _FakeSavedJobsRepo(const SavedJobsPageDto(items: [])),
        ),
      ],
    );
    addTearDown(container.dispose);

    final summary = await container.read(feedSummaryControllerProvider.future);
    expect(summary.applicationsApprox, isTrue);
    expect(summary.savedApprox, isFalse);
  });

  test('empty pages yield an all-zero summary', () async {
    final container = ProviderContainer(
      overrides: [
        applicationsRepositoryProvider.overrideWithValue(
          _FakeApplicationsRepo(const ApplicationsPageDto(items: [])),
        ),
        savedJobsRepositoryProvider.overrideWithValue(
          _FakeSavedJobsRepo(const SavedJobsPageDto(items: [])),
        ),
      ],
    );
    addTearDown(container.dispose);

    final summary = await container.read(feedSummaryControllerProvider.future);
    expect(summary.applicationsCount, 0);
    expect(summary.savedCount, 0);
  });
}
