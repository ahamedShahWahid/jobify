import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/jobs/applicant_of_job_dto.dart';

void main() {
  group('ApplicantOfJobDto.fromJson', () {
    test('parses a full row with all optional fields present', () {
      final json = <String, dynamic>{
        'application_id': 'app-1',
        'applicant_id': 'apt-1',
        'display_name': 'Jane Doe',
        'email': 'jane@example.com',
        'status': 'applied',
        'applied_at': '2026-05-20T08:30:00Z',
        'match_score': 0.78,
        'match_explanation': {
          'fit': 'Strong match for the role.',
          'caveat': 'Limited DevOps experience.',
        },
      };

      final dto = ApplicantOfJobDto.fromJson(json);

      expect(dto.applicationId, 'app-1');
      expect(dto.applicantId, 'apt-1');
      expect(dto.displayName, 'Jane Doe');
      expect(dto.email, 'jane@example.com');
      expect(dto.status, 'applied');
      expect(dto.appliedAt, DateTime.utc(2026, 5, 20, 8, 30));
      expect(dto.matchScore, closeTo(0.78, 0.001));
      expect(dto.matchExplanation, {
        'fit': 'Strong match for the role.',
        'caveat': 'Limited DevOps experience.',
      });
    });

    test('parses a minimal row with all nullable fields as null', () {
      final json = <String, dynamic>{
        'application_id': 'app-2',
        'applicant_id': 'apt-2',
        'display_name': null,
        'email': null,
        'status': 'withdrawn',
        'applied_at': '2026-06-01T12:00:00Z',
        'match_score': null,
        'match_explanation': null,
      };

      final dto = ApplicantOfJobDto.fromJson(json);

      expect(dto.applicationId, 'app-2');
      expect(dto.applicantId, 'apt-2');
      expect(dto.displayName, isNull);
      expect(dto.email, isNull);
      expect(dto.status, 'withdrawn');
      expect(dto.matchScore, isNull);
      expect(dto.matchExplanation, isNull);
    });
  });

  group('ApplicantsOfJobPageDto.fromJson', () {
    test('parses items list and next_cursor', () {
      final json = <String, dynamic>{
        'items': [
          {
            'application_id': 'app-3',
            'applicant_id': 'apt-3',
            'display_name': 'Bob Smith',
            'email': 'bob@example.com',
            'status': 'applied',
            'applied_at': '2026-05-15T10:00:00Z',
            'match_score': null,
            'match_explanation': null,
          }
        ],
        'next_cursor': 'cursor-xyz',
      };

      final page = ApplicantsOfJobPageDto.fromJson(json);

      expect(page.items, hasLength(1));
      expect(page.items.first.applicationId, 'app-3');
      expect(page.nextCursor, 'cursor-xyz');
    });

    test('parses empty page with null cursor', () {
      final json = <String, dynamic>{
        'items': <dynamic>[],
        'next_cursor': null,
      };

      final page = ApplicantsOfJobPageDto.fromJson(json);
      expect(page.items, isEmpty);
      expect(page.nextCursor, isNull);
    });
  });
}
