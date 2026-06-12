import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/jobs/recruiter_job_dto.dart';

void main() {
  group('RecruiterJobDto.fromJson', () {
    test('parses a full RecruiterJobRow (with counts and non-null CTCs)', () {
      final json = <String, dynamic>{
        'id': 'job-1',
        'title': 'Senior Flutter Engineer',
        'description': 'Build great apps.',
        'locations': ['Bangalore', 'Remote'],
        'min_exp_years': 3,
        'max_exp_years': 7,
        'ctc_min': 1200000.0,
        'ctc_max': 2000000.5,
        'status': 'open',
        'posted_at': '2026-05-01T10:00:00Z',
        'employer_verified': true,
        'applicant_count': 12,
        'surfaced_match_count': 5,
      };

      final dto = RecruiterJobDto.fromJson(json);

      expect(dto.id, 'job-1');
      expect(dto.title, 'Senior Flutter Engineer');
      expect(dto.description, 'Build great apps.');
      expect(dto.locations, ['Bangalore', 'Remote']);
      expect(dto.minExpYears, 3);
      expect(dto.maxExpYears, 7);
      expect(dto.ctcMin, 1200000.0);
      expect(dto.ctcMax, 2000000.5);
      expect(dto.status, 'open');
      expect(dto.postedAt, DateTime.utc(2026, 5, 1, 10));
      expect(dto.employerVerified, isTrue);
      expect(dto.applicantCount, 12);
      expect(dto.surfacedMatchCount, 5);
    });

    test(
        'parses a plain JobRead (no count fields) — '
        'defaults to 0 for both counts', () {
      // POST /v1/jobs and PATCH /v1/jobs/{id} return JobRead without counts.
      final json = <String, dynamic>{
        'id': 'job-2',
        'title': 'Backend Engineer',
        'description': 'Python APIs.',
        'locations': ['Mumbai'],
        'min_exp_years': 1,
        'max_exp_years': 4,
        'ctc_min': null,
        'ctc_max': null,
        'status': 'open',
        'posted_at': '2026-06-01T09:00:00Z',
        'employer_verified': false,
        // 'applicant_count' and 'surfaced_match_count' intentionally absent
      };

      final dto = RecruiterJobDto.fromJson(json);

      expect(dto.applicantCount, 0);
      expect(dto.surfacedMatchCount, 0);
    });

    test('parses a row with null CTC fields', () {
      final json = <String, dynamic>{
        'id': 'job-3',
        'title': 'Intern',
        'description': 'Internship role.',
        'locations': <String>[],
        'min_exp_years': 0,
        'max_exp_years': 1,
        'ctc_min': null,
        'ctc_max': null,
        'status': 'open',
        'posted_at': '2026-06-01T00:00:00Z',
        'employer_verified': false,
        'applicant_count': 0,
        'surfaced_match_count': 0,
      };

      final dto = RecruiterJobDto.fromJson(json);

      expect(dto.ctcMin, isNull);
      expect(dto.ctcMax, isNull);
      expect(dto.applicantCount, 0);
    });
  });

  group('RecruiterJobsPageDto.fromJson', () {
    test('parses items list and next_cursor', () {
      final json = <String, dynamic>{
        'items': [
          {
            'id': 'j1',
            'title': 'T1',
            'description': 'D1',
            'locations': <String>[],
            'min_exp_years': 0,
            'max_exp_years': 2,
            'ctc_min': null,
            'ctc_max': null,
            'status': 'open',
            'posted_at': '2026-01-01T00:00:00Z',
            'employer_verified': false,
            'applicant_count': 1,
            'surfaced_match_count': 0,
          }
        ],
        'next_cursor': 'cursor-abc',
      };

      final page = RecruiterJobsPageDto.fromJson(json);

      expect(page.items, hasLength(1));
      expect(page.items.first.id, 'j1');
      expect(page.nextCursor, 'cursor-abc');
    });

    test('parses page with null next_cursor', () {
      final json = <String, dynamic>{
        'items': <dynamic>[],
        'next_cursor': null,
      };

      final page = RecruiterJobsPageDto.fromJson(json);
      expect(page.items, isEmpty);
      expect(page.nextCursor, isNull);
    });
  });
}
