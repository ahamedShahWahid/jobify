import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/jobs/application_status.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';

// Pins the backend ApplicationStatus contract (core/src/jobify/db/models.py:670)
// via the real DTO that carries it — mirrors the job_status_test.dart pattern.
void main() {
  test('ApplicationDto parses both real backend ApplicationStatus values', () {
    final applied = ApplicationDto.fromJson(const {
      'id': 'app1',
      'job_id': 'j1',
      'status': 'applied',
      'source': 'feed',
      'stage': 'applied',
      'created_at': '2026-05-01T00:00:00Z',
      'updated_at': '2026-05-01T00:00:00Z',
    });
    expect(applied.status, ApplicationStatus.applied);

    final withdrawn = ApplicationDto.fromJson(const {
      'id': 'app2',
      'job_id': 'j1',
      'status': 'withdrawn',
      'source': 'detail',
      'stage': 'applied',
      'created_at': '2026-05-01T00:00:00Z',
      'updated_at': '2026-05-02T00:00:00Z',
    });
    expect(withdrawn.status, ApplicationStatus.withdrawn);
  });

  test('an unrecognised ApplicationStatus value degrades to unknown', () {
    final dto = ApplicationDto.fromJson(const {
      'id': 'app3',
      'job_id': 'j1',
      'status': 'expired',
      'source': 'feed',
      'stage': 'applied',
      'created_at': '2026-05-01T00:00:00Z',
      'updated_at': '2026-05-01T00:00:00Z',
    });
    expect(dto.status, ApplicationStatus.unknown);
  });
}
