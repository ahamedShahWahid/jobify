import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/core/error/exceptions.dart';
import 'package:jobify_app/data/jobs/application_stage.dart';
import 'package:jobify_app/data/jobs/recruiter_jobs_api.dart';
import 'package:jobify_app/data/jobs/recruiter_jobs_repository_impl.dart';

import '../../../helpers/mock_interceptor.dart';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

Map<String, dynamic> _jobJson(String id) => {
      'id': id,
      'title': 'Engineer',
      'description': 'Description',
      'locations': ['Bangalore'],
      'min_exp_years': 2,
      'max_exp_years': 5,
      'ctc_min': null,
      'ctc_max': null,
      'status': 'open',
      'posted_at': '2026-05-01T00:00:00Z',
      'employer_verified': true,
      'applicant_count': 3,
      'surfaced_match_count': 1,
    };

Map<String, dynamic> _pageJson(
  List<Map<String, dynamic>> items, {
  String? cursor,
}) =>
    {
      'items': items,
      'next_cursor': cursor,
    };

Map<String, dynamic> _applicantJson(String appId) => {
      'application_id': appId,
      'applicant_id': 'apt-1',
      'display_name': 'Alice',
      'email': 'alice@example.com',
      'status': 'applied',
      'stage': 'applied',
      'applied_at': '2026-05-20T08:00:00Z',
      'match_score': 0.72,
      'match_explanation': null,
    };

// ---------------------------------------------------------------------------
// MockInterceptor does NOT support setting custom response headers, so
// downloadResume tests use a _BytesInterceptor that injects a real Response
// with populated headers.
// ---------------------------------------------------------------------------

/// A minimal interceptor that resolves with bytes and a custom headers map.
class _BytesInterceptor extends Interceptor {
  _BytesInterceptor({
    required this.bytes,
    required this.responseHeaders,
  });

  final List<int> bytes;
  final Map<String, List<String>> responseHeaders;

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    handler.resolve(
      Response<List<int>>(
        requestOptions: options,
        statusCode: 200,
        data: bytes,
        headers: Headers.fromMap(responseHeaders),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  late Dio dio;
  late MockInterceptor mock;
  late RecruiterJobsRepositoryImpl repo;

  setUp(() {
    dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    mock = MockInterceptor();
    dio.interceptors.add(mock);
    repo = RecruiterJobsRepositoryImpl(RecruiterJobsApi(dio));
  });

  // -------------------------------------------------------------------------
  // listMyJobs
  // -------------------------------------------------------------------------

  group('listMyJobs', () {
    test('200 → parses page with items and nextCursor', () async {
      mock.on(
        'GET',
        '/v1/jobs/me',
        200,
        _pageJson(
          [_jobJson('j1'), _jobJson('j2')],
          cursor: 'cursor-xyz',
        ),
      );

      final page = await repo.listMyJobs();

      expect(page.items, hasLength(2));
      expect(page.items.first.id, 'j1');
      expect(page.items.first.applicantCount, 3);
      expect(page.items.first.surfacedMatchCount, 1);
      expect(page.nextCursor, 'cursor-xyz');
    });

    test('200 → empty page with null cursor', () async {
      mock.on('GET', '/v1/jobs/me', 200, _pageJson([]));

      final page = await repo.listMyJobs();

      expect(page.items, isEmpty);
      expect(page.nextCursor, isNull);
    });

    test('403 → throws ApiException', () async {
      mock.on('GET', '/v1/jobs/me', 403, {'detail': 'not_a_recruiter'});

      await expectLater(
        repo.listMyJobs(),
        throwsA(
          isA<ApiException>()
              .having((e) => e.statusCode, 'statusCode', 403)
              .having((e) => e.slug, 'slug', 'not_a_recruiter'),
        ),
      );
    });
  });

  // -------------------------------------------------------------------------
  // createJob
  // -------------------------------------------------------------------------

  group('createJob', () {
    test('201 → parses RecruiterJobDto (no counts in response)', () async {
      // POST /v1/jobs returns JobRead without the count fields.
      final responseJson = Map<String, dynamic>.from(_jobJson('j-new'))
        ..remove('applicant_count')
        ..remove('surfaced_match_count');
      mock.on('POST', '/v1/jobs', 201, responseJson);

      final result = await repo.createJob({
        'title': 'Engineer',
        'description': 'Description',
        'locations': ['Bangalore'],
        'min_exp_years': 2,
        'max_exp_years': 5,
      });

      expect(result.id, 'j-new');
      // Counts default to 0 when missing from the response.
      expect(result.applicantCount, 0);
      expect(result.surfacedMatchCount, 0);
    });

    test('422 → throws ApiException', () async {
      mock.on('POST', '/v1/jobs', 422, {'detail': 'validation_error'});

      await expectLater(
        repo.createJob({}),
        throwsA(
          isA<ApiException>().having((e) => e.statusCode, 'statusCode', 422),
        ),
      );
    });
  });

  // -------------------------------------------------------------------------
  // listApplicants
  // -------------------------------------------------------------------------

  group('listApplicants', () {
    test('200 → parses ApplicantsOfJobPageDto', () async {
      mock.on(
        'GET',
        '/v1/jobs/j1/applicants',
        200,
        {
          'items': [_applicantJson('app-1'), _applicantJson('app-2')],
          'next_cursor': null,
        },
      );

      final page = await repo.listApplicants('j1');

      expect(page.items, hasLength(2));
      expect(page.items.first.applicationId, 'app-1');
      expect(page.items.first.displayName, 'Alice');
      expect(page.items.first.matchScore, closeTo(0.72, 0.001));
      expect(page.nextCursor, isNull);
    });

    test('404 → throws ApiException', () async {
      mock.on(
        'GET',
        '/v1/jobs/missing/applicants',
        404,
        {'detail': 'not_found'},
      );

      await expectLater(
        repo.listApplicants('missing'),
        throwsA(
          isA<ApiException>().having((e) => e.statusCode, 'statusCode', 404),
        ),
      );
    });
  });

  // -------------------------------------------------------------------------
  // downloadResume
  // -------------------------------------------------------------------------
  //
  // MockInterceptor does not support custom response headers, so we use a
  // separate Dio instance with _BytesInterceptor to test the header-parsing
  // path.
  // -------------------------------------------------------------------------

  group('downloadResume', () {
    test('returns bytes + filename parsed from content-disposition header',
        () async {
      final pdfBytes = [0x25, 0x50, 0x44, 0x46]; // %PDF magic bytes
      final headersDio = Dio(BaseOptions(baseUrl: 'http://test.local'));
      headersDio.interceptors.add(
        _BytesInterceptor(
          bytes: pdfBytes,
          responseHeaders: {
            'content-disposition': ['attachment; filename="my_resume.pdf"'],
            'content-type': ['application/pdf'],
          },
        ),
      );
      final headerRepo =
          RecruiterJobsRepositoryImpl(RecruiterJobsApi(headersDio));

      final download = await headerRepo.downloadResume('app-1');

      expect(download.bytes, equals(pdfBytes));
      expect(download.filename, 'my_resume.pdf');
      expect(download.contentType, 'application/pdf');
    });

    test('falls back to "resume" filename when content-disposition is absent',
        () async {
      final docxBytes = [0x50, 0x4B, 0x03, 0x04]; // PK header (ZIP/DOCX)
      final headersDio = Dio(BaseOptions(baseUrl: 'http://test.local'));
      headersDio.interceptors.add(
        _BytesInterceptor(
          bytes: docxBytes,
          responseHeaders: {
            'content-type': [
              // ignore: lines_longer_than_80_chars
              'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            ],
          },
        ),
      );
      final noHeaderRepo =
          RecruiterJobsRepositoryImpl(RecruiterJobsApi(headersDio));

      final download = await noHeaderRepo.downloadResume('app-2');

      expect(download.bytes, equals(docxBytes));
      expect(download.filename, 'resume');
      expect(download.contentType, contains('wordprocessingml'));
    });

    test('401 → throws AuthException', () async {
      mock.on(
        'GET',
        '/v1/applications/app-bad/resume',
        401,
        {'detail': 'invalid_access_token'},
      );

      await expectLater(
        repo.downloadResume('app-bad'),
        throwsA(isA<AuthException>()),
      );
    });
  });

  // -------------------------------------------------------------------------
  // deleteJob
  // -------------------------------------------------------------------------

  group('deleteJob', () {
    test('204 → completes without error', () async {
      mock.on('DELETE', '/v1/jobs/j1', 204, null);
      await expectLater(repo.deleteJob('j1'), completes);
    });
  });

  // -------------------------------------------------------------------------
  // patchJob
  // -------------------------------------------------------------------------

  group('patchJob', () {
    test('200 → parses updated RecruiterJobDto', () async {
      final responseJson = Map<String, dynamic>.from(_jobJson('j1'));
      responseJson['title'] = 'Senior Engineer';
      mock.on('PATCH', '/v1/jobs/j1', 200, responseJson);

      final result = await repo.patchJob('j1', {'title': 'Senior Engineer'});

      expect(result.id, 'j1');
      expect(result.title, 'Senior Engineer');
    });

    test('404 → throws ApiException', () async {
      mock.on('PATCH', '/v1/jobs/missing', 404, {'detail': 'not_found'});

      await expectLater(
        repo.patchJob('missing', {}),
        throwsA(
          isA<ApiException>().having((e) => e.statusCode, 'statusCode', 404),
        ),
      );
    });
  });

  // -------------------------------------------------------------------------
  // setStage
  // -------------------------------------------------------------------------

  group('setStage', () {
    test('200 → sends wireValue and completes', () async {
      mock.on(
        'PATCH',
        '/v1/jobs/j1/applications/app-1/stage',
        200,
        {'detail': 'ok'},
      );

      await expectLater(
        repo.setStage('j1', 'app-1', ApplicationStage.shortlisted),
        completes,
      );
    });

    test('400 invalid_transition → throws ApiException', () async {
      mock.on(
        'PATCH',
        '/v1/jobs/j1/applications/app-1/stage',
        400,
        {'detail': 'invalid_transition'},
      );

      await expectLater(
        repo.setStage('j1', 'app-1', ApplicationStage.hired),
        throwsA(
          isA<ApiException>().having((e) => e.statusCode, 'statusCode', 400),
        ),
      );
    });
  });
}
