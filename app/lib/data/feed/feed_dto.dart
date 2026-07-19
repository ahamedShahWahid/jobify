import 'package:jobify_app/data/feed/match_feedback_rating.dart';
import 'package:jobify_app/data/feed/match_generator.dart';
import 'package:jobify_app/data/jobs/job_status.dart';
import 'package:json_annotation/json_annotation.dart';

part 'feed_dto.g.dart';

@JsonSerializable()
class FeedPageDto {
  const FeedPageDto({
    required this.items,
    this.nextCursor,
  });

  factory FeedPageDto.fromJson(Map<String, dynamic> json) =>
      _$FeedPageDtoFromJson(json);

  final List<FeedItemDto> items;
  final String? nextCursor;

  Map<String, dynamic> toJson() => _$FeedPageDtoToJson(this);
}

@JsonSerializable()
class FeedItemDto {
  const FeedItemDto({
    required this.match,
    required this.job,
    required this.employer,
  });

  factory FeedItemDto.fromJson(Map<String, dynamic> json) =>
      _$FeedItemDtoFromJson(json);

  final MatchSummaryDto match;
  final JobSummaryDto job;
  final EmployerSummaryDto employer;

  Map<String, dynamic> toJson() => _$FeedItemDtoToJson(this);
}

@JsonSerializable()
class MatchSummaryDto {
  const MatchSummaryDto({
    required this.id,
    required this.totalScore,
    required this.scoreComponents,
    this.explanation,
    this.surfacedAt,
    this.myFeedback,
  });

  factory MatchSummaryDto.fromJson(Map<String, dynamic> json) =>
      _$MatchSummaryDtoFromJson(json);

  final String id;
  final double totalScore;
  // Backend serializes this field as `components` (its Pydantic
  // validation_alias does NOT change the output key).
  @JsonKey(name: 'components')
  final Map<String, dynamic> scoreComponents;
  final ExplanationDto? explanation;
  final DateTime? surfacedAt;

  /// The current applicant's rating; null = unrated. Only `up`/null appear in
  /// the feed (down is server-excluded); job detail may carry `down`.
  @JsonKey(unknownEnumValue: MatchFeedbackRating.unknown)
  final MatchFeedbackRating? myFeedback;

  Map<String, dynamic> toJson() => _$MatchSummaryDtoToJson(this);
}

@JsonSerializable()
class ExplanationDto {
  const ExplanationDto({
    required this.fit,
    required this.generator,
    required this.generatorVersion,
    this.caveat,
  });

  factory ExplanationDto.fromJson(Map<String, dynamic> json) =>
      _$ExplanationDtoFromJson(json);

  final String fit;
  @JsonKey(unknownEnumValue: MatchGenerator.unknown)
  final MatchGenerator generator;
  final String generatorVersion;
  final String? caveat;

  Map<String, dynamic> toJson() => _$ExplanationDtoToJson(this);
}

@JsonSerializable()
class JobSummaryDto {
  const JobSummaryDto({
    required this.id,
    required this.title,
    required this.status,
    required this.postedAt,
    this.locations = const [],
    this.description,
  });

  factory JobSummaryDto.fromJson(Map<String, dynamic> json) =>
      _$JobSummaryDtoFromJson(json);

  final String id;
  final String title;
  // Backend JobRead sends `locations` (a list), not a singular `location`.
  final List<String> locations;
  @JsonKey(unknownEnumValue: JobStatus.unknown)
  final JobStatus status;
  final DateTime postedAt;
  final String? description;

  Map<String, dynamic> toJson() => _$JobSummaryDtoToJson(this);
}

@JsonSerializable()
class EmployerSummaryDto {
  const EmployerSummaryDto({
    required this.id,
    required this.name,
    this.verified = false,
  });

  factory EmployerSummaryDto.fromJson(Map<String, dynamic> json) =>
      _$EmployerSummaryDtoFromJson(json);

  final String id;
  final String name;
  // Backend EmployerRead sends a boolean `verified`, not a `verified_at`.
  final bool verified;

  Map<String, dynamic> toJson() => _$EmployerSummaryDtoToJson(this);
}
