import 'package:json_annotation/json_annotation.dart';

/// Applicant verdict on a surfaced match.
///
/// Mirrors backend `MatchFeedbackRating` in `core/src/jobify/db/models.py`
/// (wire: "up" / "down"); pinned by test/unit/data/feed/match_feedback_test.dart.
/// `unknown` is the unrecognised-server-value sentinel — it must NEVER
/// serialize (wireValue throws), same contract as DesiredRole.
enum MatchFeedbackRating {
  @JsonValue('up')
  up,
  @JsonValue('down')
  down,
  unknown,
}

extension MatchFeedbackRatingWire on MatchFeedbackRating {
  String get wireValue => switch (this) {
        MatchFeedbackRating.up => 'up',
        MatchFeedbackRating.down => 'down',
        MatchFeedbackRating.unknown =>
          throw StateError('MatchFeedbackRating.unknown is not a wire value'),
      };
}
