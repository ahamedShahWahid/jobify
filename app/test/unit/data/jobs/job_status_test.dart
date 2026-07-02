import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/jobs/job_status.dart';

// Pins the backend JobStatus contract (core/src/jobify/db/models.py:404) via
// the real DTO that carries it. A backend enum rename/addition with no
// matching client update fails here, not as a silent unknownEnumValue
// fallback discovered in prod.
void main() {
  test('JobSummaryDto parses both real backend JobStatus values', () {
    final open = JobSummaryDto.fromJson(const {
      'id': 'j1',
      'title': 'Backend Engineer',
      'locations': ['Bengaluru'],
      'status': 'open',
      'posted_at': '2026-05-01T00:00:00Z',
    });
    expect(open.status, JobStatus.open);

    final closed = JobSummaryDto.fromJson(const {
      'id': 'j2',
      'title': 'Backend Engineer',
      'locations': ['Bengaluru'],
      'status': 'closed',
      'posted_at': '2026-05-01T00:00:00Z',
    });
    expect(closed.status, JobStatus.closed);
  });

  test('an unrecognised JobStatus value degrades to the unknown sentinel', () {
    final dto = JobSummaryDto.fromJson(const {
      'id': 'j3',
      'title': 'Backend Engineer',
      'locations': ['Bengaluru'],
      'status': 'archived',
      'posted_at': '2026-05-01T00:00:00Z',
    });
    expect(dto.status, JobStatus.unknown);
  });
}
