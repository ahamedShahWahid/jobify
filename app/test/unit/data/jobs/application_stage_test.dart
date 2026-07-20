import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/jobs/application_stage.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';

void main() {
  group('ApplicationStage wire map', () {
    test('round-trips every real value', () {
      const wire = {
        ApplicationStage.applied: 'applied',
        ApplicationStage.shortlisted: 'shortlisted',
        ApplicationStage.interview: 'interview',
        ApplicationStage.offer: 'offer',
        ApplicationStage.hired: 'hired',
        ApplicationStage.rejected: 'rejected',
      };
      for (final e in wire.entries) {
        expect(e.key.wireValue, e.value);
      }
    });

    test('unknown never serializes', () {
      expect(() => ApplicationStage.unknown.wireValue, throwsStateError);
    });
  });

  group('ApplicationDto.stage', () {
    Map<String, dynamic> appJson(String stage) => {
          'id': 'a1',
          'job_id': 'j1',
          'status': 'applied',
          'source': 'feed',
          'stage': stage,
          'created_at': '2026-07-19T00:00:00Z',
          'updated_at': '2026-07-19T00:00:00Z',
        };

    test('parses a real stage', () {
      expect(
        ApplicationDto.fromJson(appJson('interview')).stage,
        ApplicationStage.interview,
      );
    });

    test('unrecognised server value degrades to unknown', () {
      expect(
        ApplicationDto.fromJson(appJson('meh')).stage,
        ApplicationStage.unknown,
      );
    });
  });

  group('StageEventDto', () {
    test('parses the timeline item shape', () {
      final dto = StageEventDto.fromJson({
        'from_stage': 'applied',
        'to_stage': 'shortlisted',
        'created_at': '2026-07-19T00:00:00Z',
      });
      expect(dto.fromStage, ApplicationStage.applied);
      expect(dto.toStage, ApplicationStage.shortlisted);
    });
  });
}
