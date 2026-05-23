// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'feed_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_FeedPageDto _$FeedPageDtoFromJson(Map<String, dynamic> json) => _FeedPageDto(
      items: (json['items'] as List<dynamic>)
          .map((e) => FeedItemDto.fromJson(e as Map<String, dynamic>))
          .toList(),
      nextCursor: json['next_cursor'] as String?,
    );

Map<String, dynamic> _$FeedPageDtoToJson(_FeedPageDto instance) =>
    <String, dynamic>{
      'items': instance.items.map((e) => e.toJson()).toList(),
      'next_cursor': instance.nextCursor,
    };

_FeedItemDto _$FeedItemDtoFromJson(Map<String, dynamic> json) => _FeedItemDto(
      match: MatchSummaryDto.fromJson(json['match'] as Map<String, dynamic>),
      job: JobSummaryDto.fromJson(json['job'] as Map<String, dynamic>),
      employer:
          EmployerSummaryDto.fromJson(json['employer'] as Map<String, dynamic>),
    );

Map<String, dynamic> _$FeedItemDtoToJson(_FeedItemDto instance) =>
    <String, dynamic>{
      'match': instance.match.toJson(),
      'job': instance.job.toJson(),
      'employer': instance.employer.toJson(),
    };

_MatchSummaryDto _$MatchSummaryDtoFromJson(Map<String, dynamic> json) =>
    _MatchSummaryDto(
      id: json['id'] as String,
      totalScore: (json['total_score'] as num).toDouble(),
      scoreComponents: json['score_components'] as Map<String, dynamic>,
      explanation: json['explanation'] == null
          ? null
          : ExplanationDto.fromJson(
              json['explanation'] as Map<String, dynamic>),
      surfacedAt: json['surfaced_at'] == null
          ? null
          : DateTime.parse(json['surfaced_at'] as String),
    );

Map<String, dynamic> _$MatchSummaryDtoToJson(_MatchSummaryDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'total_score': instance.totalScore,
      'score_components': instance.scoreComponents,
      'explanation': instance.explanation?.toJson(),
      'surfaced_at': instance.surfacedAt?.toIso8601String(),
    };

_ExplanationDto _$ExplanationDtoFromJson(Map<String, dynamic> json) =>
    _ExplanationDto(
      fit: json['fit'] as String,
      generator: json['generator'] as String,
      generatorVersion: json['generator_version'] as String,
      caveat: json['caveat'] as String?,
    );

Map<String, dynamic> _$ExplanationDtoToJson(_ExplanationDto instance) =>
    <String, dynamic>{
      'fit': instance.fit,
      'generator': instance.generator,
      'generator_version': instance.generatorVersion,
      'caveat': instance.caveat,
    };

_JobSummaryDto _$JobSummaryDtoFromJson(Map<String, dynamic> json) =>
    _JobSummaryDto(
      id: json['id'] as String,
      title: json['title'] as String,
      location: json['location'] as String,
      status: json['status'] as String,
      postedAt: DateTime.parse(json['posted_at'] as String),
      description: json['description'] as String?,
    );

Map<String, dynamic> _$JobSummaryDtoToJson(_JobSummaryDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'title': instance.title,
      'location': instance.location,
      'status': instance.status,
      'posted_at': instance.postedAt.toIso8601String(),
      'description': instance.description,
    };

_EmployerSummaryDto _$EmployerSummaryDtoFromJson(Map<String, dynamic> json) =>
    _EmployerSummaryDto(
      id: json['id'] as String,
      name: json['name'] as String,
      verifiedAt: json['verified_at'] == null
          ? null
          : DateTime.parse(json['verified_at'] as String),
    );

Map<String, dynamic> _$EmployerSummaryDtoToJson(_EmployerSummaryDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'name': instance.name,
      'verified_at': instance.verifiedAt?.toIso8601String(),
    };
