// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'feed_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

FeedPageDto _$FeedPageDtoFromJson(Map<String, dynamic> json) => FeedPageDto(
      items: (json['items'] as List<dynamic>)
          .map((e) => FeedItemDto.fromJson(e as Map<String, dynamic>))
          .toList(),
      nextCursor: json['next_cursor'] as String?,
    );

Map<String, dynamic> _$FeedPageDtoToJson(FeedPageDto instance) =>
    <String, dynamic>{
      'items': instance.items.map((e) => e.toJson()).toList(),
      'next_cursor': instance.nextCursor,
    };

FeedItemDto _$FeedItemDtoFromJson(Map<String, dynamic> json) => FeedItemDto(
      match: MatchSummaryDto.fromJson(json['match'] as Map<String, dynamic>),
      job: JobSummaryDto.fromJson(json['job'] as Map<String, dynamic>),
      employer:
          EmployerSummaryDto.fromJson(json['employer'] as Map<String, dynamic>),
    );

Map<String, dynamic> _$FeedItemDtoToJson(FeedItemDto instance) =>
    <String, dynamic>{
      'match': instance.match.toJson(),
      'job': instance.job.toJson(),
      'employer': instance.employer.toJson(),
    };

MatchSummaryDto _$MatchSummaryDtoFromJson(Map<String, dynamic> json) =>
    MatchSummaryDto(
      id: json['id'] as String,
      totalScore: (json['total_score'] as num).toDouble(),
      scoreComponents: json['components'] as Map<String, dynamic>,
      explanation: json['explanation'] == null
          ? null
          : ExplanationDto.fromJson(
              json['explanation'] as Map<String, dynamic>),
      surfacedAt: json['surfaced_at'] == null
          ? null
          : DateTime.parse(json['surfaced_at'] as String),
      myFeedback: $enumDecodeNullable(
          _$MatchFeedbackRatingEnumMap, json['my_feedback'],
          unknownValue: MatchFeedbackRating.unknown),
    );

Map<String, dynamic> _$MatchSummaryDtoToJson(MatchSummaryDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'total_score': instance.totalScore,
      'components': instance.scoreComponents,
      'explanation': instance.explanation?.toJson(),
      'surfaced_at': instance.surfacedAt?.toIso8601String(),
      'my_feedback': _$MatchFeedbackRatingEnumMap[instance.myFeedback],
    };

const _$MatchFeedbackRatingEnumMap = {
  MatchFeedbackRating.up: 'up',
  MatchFeedbackRating.down: 'down',
  MatchFeedbackRating.unknown: 'unknown',
};

ExplanationDto _$ExplanationDtoFromJson(Map<String, dynamic> json) =>
    ExplanationDto(
      fit: json['fit'] as String,
      generator: $enumDecode(_$MatchGeneratorEnumMap, json['generator'],
          unknownValue: MatchGenerator.unknown),
      generatorVersion: json['generator_version'] as String,
      caveat: json['caveat'] as String?,
    );

Map<String, dynamic> _$ExplanationDtoToJson(ExplanationDto instance) =>
    <String, dynamic>{
      'fit': instance.fit,
      'generator': _$MatchGeneratorEnumMap[instance.generator]!,
      'generator_version': instance.generatorVersion,
      'caveat': instance.caveat,
    };

const _$MatchGeneratorEnumMap = {
  MatchGenerator.templated: 'templated',
  MatchGenerator.llm: 'llm',
  MatchGenerator.unknown: 'unknown',
};

JobSummaryDto _$JobSummaryDtoFromJson(Map<String, dynamic> json) =>
    JobSummaryDto(
      id: json['id'] as String,
      title: json['title'] as String,
      status: $enumDecode(_$JobStatusEnumMap, json['status'],
          unknownValue: JobStatus.unknown),
      postedAt: DateTime.parse(json['posted_at'] as String),
      locations: (json['locations'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          const [],
      description: json['description'] as String?,
    );

Map<String, dynamic> _$JobSummaryDtoToJson(JobSummaryDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'title': instance.title,
      'locations': instance.locations,
      'status': _$JobStatusEnumMap[instance.status]!,
      'posted_at': instance.postedAt.toIso8601String(),
      'description': instance.description,
    };

const _$JobStatusEnumMap = {
  JobStatus.open: 'open',
  JobStatus.closed: 'closed',
  JobStatus.unknown: 'unknown',
};

EmployerSummaryDto _$EmployerSummaryDtoFromJson(Map<String, dynamic> json) =>
    EmployerSummaryDto(
      id: json['id'] as String,
      name: json['name'] as String,
      verified: json['verified'] as bool? ?? false,
    );

Map<String, dynamic> _$EmployerSummaryDtoToJson(EmployerSummaryDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'name': instance.name,
      'verified': instance.verified,
    };
