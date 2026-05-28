import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/resume/resume_api.dart';
import 'package:kpa_app/data/resume/resume_parse_status.dart';
import 'package:kpa_app/data/resume/resume_repository_impl.dart';

import '../../../helpers/mock_interceptor.dart';

Map<String, dynamic> _resumeJson(String id, String name, String status) => {
      'id': id,
      'applicant_id': 'a1',
      'original_filename': name,
      'content_type': 'application/pdf',
      'size_bytes': 10,
      'parse_status': status,
      'created_at': '2026-05-01T00:00:00Z',
    };

void main() {
  test('current(): returns first of GET list (newest), or null when empty',
      () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    final mock = MockInterceptor();
    dio.interceptors.add(mock);
    mock.onList('GET', '/v1/applicants/me/resumes', 200, [
      _resumeJson('r2', 'two.pdf', 'parsed'),
      _resumeJson('r1', 'one.pdf', 'failed'),
    ]);
    final repo = ResumeRepositoryImpl(ResumeApi(dio));
    final current = await repo.current();
    expect(current?.id, 'r2');
    expect(current?.parseStatus, ResumeParseStatus.parsed);
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
