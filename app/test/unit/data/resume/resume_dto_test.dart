import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/resume/resume_dto.dart';
import 'package:jobify_app/data/resume/resume_parse_status.dart';

void main() {
  test('parses the ResumeRead wire shape', () {
    final dto = ResumeDto.fromJson(const {
      'id': 'r1',
      'applicant_id': 'a1',
      'original_filename': 'cv.pdf',
      'content_type': 'application/pdf',
      'size_bytes': 1234,
      'parse_status': 'parsed',
      'created_at': '2026-05-01T00:00:00Z',
    });
    expect(dto.id, 'r1');
    expect(dto.applicantId, 'a1');
    expect(dto.originalFilename, 'cv.pdf');
    expect(dto.sizeBytes, 1234);
    expect(dto.parseStatus, ResumeParseStatus.parsed);
  });

  test('unknown parse_status → sentinel', () {
    final dto = ResumeDto.fromJson(const {
      'id': 'r1',
      'applicant_id': 'a1',
      'original_filename': 'cv.pdf',
      'content_type': 'application/pdf',
      'size_bytes': 1,
      'parse_status': 'martian',
      'created_at': '2026-05-01T00:00:00Z',
    });
    expect(dto.parseStatus, ResumeParseStatus.unknown);
  });
}
