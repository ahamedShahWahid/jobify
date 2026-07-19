import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/feed/match_feedback_dto.dart';
import 'package:jobify_app/data/feed/match_feedback_rating.dart';

void main() {
  group('MatchFeedbackRating wire map', () {
    test('round-trips every real value', () {
      expect(MatchFeedbackRating.up.wireValue, 'up');
      expect(MatchFeedbackRating.down.wireValue, 'down');
    });

    test('unknown never serializes', () {
      expect(() => MatchFeedbackRating.unknown.wireValue, throwsStateError);
    });
  });

  group('MatchSummaryDto.my_feedback', () {
    Map<String, dynamic> matchJson(Object? myFeedback) => {
          'id': 'm1',
          'total_score': 0.8,
          'components': {'location': 1.0},
          'explanation': null,
          'surfaced_at': '2026-07-19T00:00:00Z',
          'my_feedback': myFeedback,
        };

    test('null stays null', () {
      expect(MatchSummaryDto.fromJson(matchJson(null)).myFeedback, isNull);
    });

    test('up parses', () {
      expect(
        MatchSummaryDto.fromJson(matchJson('up')).myFeedback,
        MatchFeedbackRating.up,
      );
    });

    test('unrecognised server value degrades to unknown, not a throw', () {
      expect(
        MatchSummaryDto.fromJson(matchJson('meh')).myFeedback,
        MatchFeedbackRating.unknown,
      );
    });
  });

  group('MatchFeedbackDto', () {
    test('parses the PUT response shape', () {
      final dto = MatchFeedbackDto.fromJson({
        'id': 'f1',
        'job_id': 'j1',
        'rating': 'down',
        'created_at': '2026-07-19T00:00:00Z',
        'updated_at': '2026-07-19T00:00:00Z',
      });
      expect(dto.rating, MatchFeedbackRating.down);
      expect(dto.jobId, 'j1');
    });
  });
}
