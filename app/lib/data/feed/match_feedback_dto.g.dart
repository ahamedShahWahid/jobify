// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'match_feedback_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

MatchFeedbackDto _$MatchFeedbackDtoFromJson(Map<String, dynamic> json) =>
    MatchFeedbackDto(
      id: json['id'] as String,
      jobId: json['job_id'] as String,
      rating: $enumDecode(_$MatchFeedbackRatingEnumMap, json['rating'],
          unknownValue: MatchFeedbackRating.unknown),
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );

Map<String, dynamic> _$MatchFeedbackDtoToJson(MatchFeedbackDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'job_id': instance.jobId,
      'rating': _$MatchFeedbackRatingEnumMap[instance.rating]!,
      'created_at': instance.createdAt.toIso8601String(),
      'updated_at': instance.updatedAt.toIso8601String(),
    };

const _$MatchFeedbackRatingEnumMap = {
  MatchFeedbackRating.up: 'up',
  MatchFeedbackRating.down: 'down',
  MatchFeedbackRating.unknown: 'unknown',
};
