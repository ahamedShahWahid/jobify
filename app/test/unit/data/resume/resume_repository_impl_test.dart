import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/resume/resume_api.dart';
import 'package:jobify_app/data/resume/resume_parse_status.dart';
import 'package:jobify_app/data/resume/resume_repository_impl.dart';

import '../../../helpers/mock_interceptor.dart';

Map<String, dynamic> _resumeJson(
  String id,
  String name,
  String status, {
  Map<String, dynamic>? parsedJson,
}) => {
  'id': id,
  'applicant_id': 'a1',
  'original_filename': name,
  'content_type': 'application/pdf',
  'size_bytes': 10,
  'parse_status': status,
  'created_at': '2026-05-01T00:00:00Z',
  if (parsedJson != null) 'parsed_json': parsedJson,
};

void main() {
  test("current(): fetches the newest list row's own detail (PERF-09: the "
      'list row has no parsedJson; every current() caller needs it)', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    final mock =
        MockInterceptor()..onList('GET', '/v1/applicants/me/resumes', 200, [
          _resumeJson('r2', 'two.pdf', 'parsed'), // no parsed_json — list shape
          _resumeJson('r1', 'one.pdf', 'failed'),
        ]);
    dio.interceptors.add(mock);
    mock.on(
      'GET',
      '/v1/applicants/me/resumes/r2',
      200,
      _resumeJson(
        'r2',
        'two.pdf',
        'parsed',
        parsedJson: {
          'skills': ['Dart'],
        },
      ),
    );
    final repo = ResumeRepositoryImpl(ResumeApi(dio));
    final current = await repo.current();
    expect(current?.id, 'r2');
    expect(current?.parseStatus, ResumeParseStatus.parsed);
    expect(current?.parsedJson, {
      'skills': ['Dart'],
    });
    expect(mock.lastRequestFor('GET', '/v1/applicants/me/resumes/r1'), isNull);
  });

  test('upload(): POSTs multipart to /resumes and parses ResumeDto', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    final mock = MockInterceptor();
    dio.interceptors.add(mock);
    mock.on(
      'POST',
      '/v1/applicants/me/resumes',
      201,
      _resumeJson('r9', 'new.pdf', 'pending'),
    );
    final repo = ResumeRepositoryImpl(ResumeApi(dio));
    final dto = await repo.upload(
      bytes: [1, 2, 3],
      filename: 'new.pdf',
      contentType: 'application/pdf',
    );
    expect(dto.id, 'r9');
    expect(dto.parseStatus, ResumeParseStatus.pending);
    final req = mock.lastRequestFor('POST', '/v1/applicants/me/resumes');
    expect(req?.data, isA<FormData>());
    final form = req!.data as FormData;
    expect(form.files.single.key, 'file');
  });

  test('current(): returns null when the list is empty', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    final mock = MockInterceptor();
    dio.interceptors.add(mock);
    mock.onList('GET', '/v1/applicants/me/resumes', 200, <dynamic>[]);
    final repo = ResumeRepositoryImpl(ResumeApi(dio));
    expect(await repo.current(), isNull);
  });
}
