import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/core/error/exceptions.dart';
import 'package:jobify_app/data/jobs/application_stage.dart';
import 'package:jobify_app/data/jobs/application_status.dart';
import 'package:jobify_app/data/jobs/applications_api.dart';
import 'package:jobify_app/data/jobs/applications_repository_impl.dart';

import '../../../helpers/mock_interceptor.dart';

Map<String, dynamic> _appsPage() => {
      'items': [
        {
          'application': {
            'id': 'a1',
            'job_id': 'j1',
            'status': 'applied',
            'source': 'feed',
            'stage': 'applied',
            'created_at': '2026-05-21T12:00:00Z',
            'updated_at': '2026-05-21T12:00:00Z',
          },
          'job': {
            'id': 'j1',
            'title': 'Eng',
            'locations': ['BLR'],
            'status': 'open',
            'posted_at': '2026-05-18T00:00:00Z',
          },
          'employer': {'id': 'e1', 'name': 'Acme', 'verified': false},
        }
      ],
      'next_cursor': null,
    };

void main() {
  late Dio dio;
  late MockInterceptor mock;
  late ApplicationsRepositoryImpl repo;

  setUp(() {
    dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    mock = MockInterceptor();
    dio.interceptors.add(mock);
    repo = ApplicationsRepositoryImpl(ApplicationsApi(dio));
  });

  test('fetchPage: 200 → ApplicationsPageDto', () async {
    mock.on('GET', '/v1/applications', 200, _appsPage());
    final page = await repo.fetchPage();
    expect(page.items.single.application.id, 'a1');
  });

  test('withdraw: 200 → ApplicationDto with withdrawn status', () async {
    mock.on('PATCH', '/v1/applications/a1', 200, {
      'id': 'a1',
      'job_id': 'j1',
      'status': 'withdrawn',
      'source': 'feed',
      'stage': 'applied',
      'created_at': '2026-05-21T12:00:00Z',
      'updated_at': '2026-05-22T09:00:00Z',
    });
    final a = await repo.withdraw('a1');
    expect(a.status, ApplicationStatus.withdrawn);
    expect(a.updatedAt, isNotNull);
  });

  test('withdraw: 400 invalid_transition → ApiException', () async {
    mock.on('PATCH', '/v1/applications/a1', 400, {
      'status': 400,
      'slug': 'invalid_transition',
    });
    await expectLater(repo.withdraw('a1'), throwsA(isA<ApiException>()));
  });

  test('fetchTimeline: 200 → List<StageEventDto>', () async {
    mock.on('GET', '/v1/applications/a1/timeline', 200, {
      'items': [
        {
          'from_stage': 'applied',
          'to_stage': 'shortlisted',
          'created_at': '2026-05-21T12:00:00Z',
        },
      ],
    });
    final events = await repo.fetchTimeline('a1');
    expect(events, hasLength(1));
    expect(events.single.fromStage, ApplicationStage.applied);
    expect(events.single.toStage, ApplicationStage.shortlisted);
  });

  test('fetchTimeline: 404 → ApiException', () async {
    mock.on('GET', '/v1/applications/missing/timeline', 404, {
      'status': 404,
      'slug': 'not_found',
    });
    await expectLater(
      repo.fetchTimeline('missing'),
      throwsA(isA<ApiException>()),
    );
  });
}
