import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/core/error/exceptions.dart';
import 'package:jobify_app/data/jobs/applicant_of_job_dto.dart';
import 'package:jobify_app/data/jobs/application_stage.dart';
import 'package:jobify_app/data/jobs/recruiter_job_dto.dart';
import 'package:jobify_app/data/jobs/recruiter_jobs_api.dart';
import 'package:jobify_app/data/jobs/recruiter_jobs_repository.dart';
import 'package:jobify_app/data/jobs/recruiter_jobs_repository_impl.dart';
import 'package:jobify_app/presentation/recruiter/job_form_controller.dart';

class _FakeRepo implements RecruiterJobsRepository {
  _FakeRepo({this.throwOnCreate = false, this.throwOnPatch = false});

  final bool throwOnCreate;
  final bool throwOnPatch;

  int createCallCount = 0;
  int patchCallCount = 0;
  int deleteCallCount = 0;
  Map<String, dynamic>? lastCreateBody;
  Map<String, dynamic>? lastPatchBody;

  RecruiterJobDto _stubJob(String id) => RecruiterJobDto(
        id: id,
        title: 'T',
        description: 'D',
        locations: const ['BLR'],
        minExpYears: 1,
        maxExpYears: 3,
        status: 'open',
        postedAt: DateTime.utc(2026),
        employerVerified: true,
      );

  @override
  Future<RecruiterJobsPageDto> listMyJobs({
    String? status,
    String? cursor,
    int limit = 20,
  }) async =>
      const RecruiterJobsPageDto(items: []);

  @override
  Future<RecruiterJobDto> createJob(Map<String, dynamic> body) async {
    createCallCount++;
    lastCreateBody = Map.from(body);
    if (throwOnCreate) {
      throw const ApiException(statusCode: 500, slug: 'server_error');
    }
    return _stubJob('new-job');
  }

  @override
  Future<RecruiterJobDto> patchJob(String id, Map<String, dynamic> body) async {
    patchCallCount++;
    lastPatchBody = Map.from(body);
    if (throwOnPatch) {
      throw const ApiException(statusCode: 400, slug: 'invalid_transition');
    }
    return _stubJob(id);
  }

  @override
  Future<void> deleteJob(String id) async {
    deleteCallCount++;
  }

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

  @override
  Future<void> setStage(
    String jobId,
    String applicationId,
    ApplicationStage stage,
  ) async =>
      throw UnimplementedError();
}

const _testData = JobFormData(
  title: 'Software Engineer',
  description: 'Build things',
  locations: ['BLR', 'MUM'],
  minExpYears: 2,
  maxExpYears: 5,
  ctcMin: 800000,
  ctcMax: 1200000,
);

const _testDataNullCtc = JobFormData(
  title: 'Intern',
  description: 'Learn things',
  locations: ['BLR'],
  minExpYears: 0,
  maxExpYears: 1,
);

void main() {
  group('JobFormData.toCreateBody', () {
    test('includes employer_id and all fields with snake_case keys', () {
      final body = _testData.toCreateBody('emp-1');
      expect(body['employer_id'], 'emp-1');
      expect(body['title'], 'Software Engineer');
      expect(body['description'], 'Build things');
      expect(body['locations'], ['BLR', 'MUM']);
      expect(body['min_exp_years'], 2);
      expect(body['max_exp_years'], 5);
      expect(body['status'], 'open');
      expect(body['ctc_min'], 800000);
      expect(body['ctc_max'], 1200000);
    });

    test('omits ctc_min and ctc_max when null', () {
      final body = _testDataNullCtc.toCreateBody('emp-1');
      expect(body.containsKey('ctc_min'), isFalse);
      expect(body.containsKey('ctc_max'), isFalse);
    });
  });

  group('JobFormData.toPatchBody', () {
    test('includes all fields with snake_case keys but no employer_id', () {
      final body = _testData.toPatchBody();
      expect(body.containsKey('employer_id'), isFalse);
      expect(body['title'], 'Software Engineer');
      expect(body['min_exp_years'], 2);
      expect(body['max_exp_years'], 5);
      expect(body['status'], 'open');
      expect(body['ctc_min'], 800000);
      expect(body['ctc_max'], 1200000);
    });

    test('omits ctc_min and ctc_max when null', () {
      final body = _testDataNullCtc.toPatchBody();
      expect(body.containsKey('ctc_min'), isFalse);
      expect(body.containsKey('ctc_max'), isFalse);
    });
  });

  group('JobFormController.create', () {
    test('success: calls repo once and state hasValue', () async {
      final fake = _FakeRepo();
      final container = ProviderContainer(
        overrides: [
          recruiterJobsRepositoryProvider.overrideWithValue(fake),
        ],
      );
      addTearDown(container.dispose);

      await container
          .read(jobFormControllerProvider.notifier)
          .create(employerId: 'emp-1', data: _testData);

      expect(fake.createCallCount, 1);
      expect(container.read(jobFormControllerProvider).hasValue, isTrue);
    });

    test('success: create body sent to repo contains employer_id', () async {
      final fake = _FakeRepo();
      final container = ProviderContainer(
        overrides: [
          recruiterJobsRepositoryProvider.overrideWithValue(fake),
        ],
      );
      addTearDown(container.dispose);

      await container
          .read(jobFormControllerProvider.notifier)
          .create(employerId: 'emp-42', data: _testData);

      expect(fake.lastCreateBody!['employer_id'], 'emp-42');
    });

    test('error: state hasError when repo throws ApiException', () async {
      final fake = _FakeRepo(throwOnCreate: true);
      final container = ProviderContainer(
        overrides: [
          recruiterJobsRepositoryProvider.overrideWithValue(fake),
        ],
      );
      addTearDown(container.dispose);

      await container
          .read(jobFormControllerProvider.notifier)
          .create(employerId: 'emp-1', data: _testData);

      expect(container.read(jobFormControllerProvider).hasError, isTrue);
    });
  });

  group('JobFormController.editJob', () {
    test('success: calls patchJob once and state hasValue', () async {
      final fake = _FakeRepo();
      final container = ProviderContainer(
        overrides: [
          recruiterJobsRepositoryProvider.overrideWithValue(fake),
        ],
      );
      addTearDown(container.dispose);

      await container
          .read(jobFormControllerProvider.notifier)
          .editJob(jobId: 'job-1', data: _testData);

      expect(fake.patchCallCount, 1);
      expect(container.read(jobFormControllerProvider).hasValue, isTrue);
    });

    test('error: state hasError when patch throws', () async {
      final fake = _FakeRepo(throwOnPatch: true);
      final container = ProviderContainer(
        overrides: [
          recruiterJobsRepositoryProvider.overrideWithValue(fake),
        ],
      );
      addTearDown(container.dispose);

      await container
          .read(jobFormControllerProvider.notifier)
          .editJob(jobId: 'job-1', data: _testData);

      expect(container.read(jobFormControllerProvider).hasError, isTrue);
    });
  });

  group('JobFormController.close', () {
    test('sends status=closed and state hasValue', () async {
      final fake = _FakeRepo();
      final container = ProviderContainer(
        overrides: [
          recruiterJobsRepositoryProvider.overrideWithValue(fake),
        ],
      );
      addTearDown(container.dispose);

      await container.read(jobFormControllerProvider.notifier).close('job-1');

      expect(fake.patchCallCount, 1);
      expect(fake.lastPatchBody, {'status': 'closed'});
      expect(container.read(jobFormControllerProvider).hasValue, isTrue);
    });
  });

  group('JobFormController.delete', () {
    test('calls deleteJob once and state hasValue(null)', () async {
      final fake = _FakeRepo();
      final container = ProviderContainer(
        overrides: [
          recruiterJobsRepositoryProvider.overrideWithValue(fake),
        ],
      );
      addTearDown(container.dispose);

      await container.read(jobFormControllerProvider.notifier).delete('job-1');

      expect(fake.deleteCallCount, 1);
      expect(container.read(jobFormControllerProvider).hasValue, isTrue);
      expect(container.read(jobFormControllerProvider).value, isNull);
    });
  });
}
