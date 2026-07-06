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

class _ThrowingApplicationsRepo implements ApplicationsRepository {
  @override
  Future<ApplicationsPageDto> fetchPage({
    String? cursor,
    int limit = 20,
  }) async =>
      throw Exception('applications boom');

  @override
  Future<ApplicationDto> withdraw(String applicationId) async =>
      throw UnimplementedError();
}

class _ThrowingSavedJobsRepo implements SavedJobsRepository {
  @override
  Future<SavedJobsPageDto> fetchPage({String? cursor, int limit = 20}) async =>
      throw Exception('saved jobs boom');
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

  test(
      'both repos rejecting completes with a single clean error '
      '(no hang, no separate unhandled-rejection zone error)', () async {
    final container = ProviderContainer(
      // Riverpod's default automatic retry (up to 10 retries, 200ms-6.4s
      // backoff — riverpod's `defaultRetry`) would otherwise keep this
      // provider in a `AsyncLoading(retrying: true)` state for ~30+ seconds
      // before finally giving up; disabling it here isolates what this test
      // targets — that a single rejection (not a hang, not an unrelated
      // unhandled-rejection zone error) surfaces promptly.
      retry: (_, __) => null,
      overrides: [
        applicationsRepositoryProvider
            .overrideWithValue(_ThrowingApplicationsRepo()),
        savedJobsRepositoryProvider.overrideWithValue(_ThrowingSavedJobsRepo()),
      ],
    );
    addTearDown(container.dispose);

    // Future.wait attaches a listener to BOTH futures synchronously when
    // called, so even though both the applications and saved-jobs fetches
    // reject, neither rejection is ever left unobserved — this used to be a
    // real hazard under the old sequential-await implementation.
    Object? caught;
    try {
      await container.read(feedSummaryControllerProvider.future);
    } catch (e) {
      caught = e;
    }
    expect(caught, isA<Exception>());
  });
}
