import 'package:jobify_app/data/feed/match_feedback_rating.dart';
import 'package:json_annotation/json_annotation.dart';

part 'match_feedback_dto.g.dart';

/// Mirrors backend `MatchFeedbackRead` in
/// `api/src/jobify_api/routes/match_feedback.py`.
@JsonSerializable()
class MatchFeedbackDto {
  const MatchFeedbackDto({
    required this.id,
    required this.jobId,
    required this.rating,
    required this.createdAt,
    required this.updatedAt,
  });

  factory MatchFeedbackDto.fromJson(Map<String, dynamic> json) =>
      _$MatchFeedbackDtoFromJson(json);

  final String id;
  final String jobId;
  @JsonKey(unknownEnumValue: MatchFeedbackRating.unknown)
  final MatchFeedbackRating rating;
  final DateTime createdAt;
  final DateTime updatedAt;

  Map<String, dynamic> toJson() => _$MatchFeedbackDtoToJson(this);
}
