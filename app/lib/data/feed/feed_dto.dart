import 'package:freezed_annotation/freezed_annotation.dart';

part 'feed_dto.freezed.dart';
part 'feed_dto.g.dart';

@freezed
abstract class FeedPageDto with _$FeedPageDto {
  const factory FeedPageDto({
    required List<FeedItemDto> items,
    String? nextCursor,
  }) = _FeedPageDto;

  factory FeedPageDto.fromJson(Map<String, dynamic> json) =>
      _$FeedPageDtoFromJson(json);
}

@freezed
abstract class FeedItemDto with _$FeedItemDto {
  const factory FeedItemDto({
    required MatchSummaryDto match,
    required JobSummaryDto job,
    required EmployerSummaryDto employer,
  }) = _FeedItemDto;

  factory FeedItemDto.fromJson(Map<String, dynamic> json) =>
      _$FeedItemDtoFromJson(json);
}

@freezed
abstract class MatchSummaryDto with _$MatchSummaryDto {
  const factory MatchSummaryDto({
    required String id,
    required double totalScore,
    required Map<String, dynamic> scoreComponents,
    ExplanationDto? explanation,
    DateTime? surfacedAt,
  }) = _MatchSummaryDto;

  factory MatchSummaryDto.fromJson(Map<String, dynamic> json) =>
      _$MatchSummaryDtoFromJson(json);
}

@freezed
abstract class ExplanationDto with _$ExplanationDto {
  const factory ExplanationDto({
    required String fit,
    required String generator,
    required String generatorVersion,
    String? caveat,
  }) = _ExplanationDto;

  factory ExplanationDto.fromJson(Map<String, dynamic> json) =>
      _$ExplanationDtoFromJson(json);
}

@freezed
abstract class JobSummaryDto with _$JobSummaryDto {
  const factory JobSummaryDto({
    required String id,
    required String title,
    required String location,
    required String status,
    required DateTime postedAt,
    String? description,
  }) = _JobSummaryDto;

  factory JobSummaryDto.fromJson(Map<String, dynamic> json) =>
      _$JobSummaryDtoFromJson(json);
}

@freezed
abstract class EmployerSummaryDto with _$EmployerSummaryDto {
  const factory EmployerSummaryDto({
    required String id,
    required String name,
    DateTime? verifiedAt,
  }) = _EmployerSummaryDto;

  factory EmployerSummaryDto.fromJson(Map<String, dynamic> json) =>
      _$EmployerSummaryDtoFromJson(json);
}
