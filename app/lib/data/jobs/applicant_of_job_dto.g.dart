// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'applicant_of_job_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

ApplicantOfJobDto _$ApplicantOfJobDtoFromJson(Map<String, dynamic> json) =>
    ApplicantOfJobDto(
      applicationId: json['application_id'] as String,
      applicantId: json['applicant_id'] as String,
      status: json['status'] as String,
      stage: $enumDecode(_$ApplicationStageEnumMap, json['stage'],
          unknownValue: ApplicationStage.unknown),
      appliedAt: DateTime.parse(json['applied_at'] as String),
      displayName: json['display_name'] as String?,
      email: json['email'] as String?,
      matchScore: (json['match_score'] as num?)?.toDouble(),
      matchExplanation:
          (json['match_explanation'] as Map<String, dynamic>?)?.map(
        (k, e) => MapEntry(k, e as String),
      ),
    );

Map<String, dynamic> _$ApplicantOfJobDtoToJson(ApplicantOfJobDto instance) =>
    <String, dynamic>{
      'application_id': instance.applicationId,
      'applicant_id': instance.applicantId,
      'display_name': instance.displayName,
      'email': instance.email,
      'status': instance.status,
      'stage': _$ApplicationStageEnumMap[instance.stage]!,
      'applied_at': instance.appliedAt.toIso8601String(),
      'match_score': instance.matchScore,
      'match_explanation': instance.matchExplanation,
    };

const _$ApplicationStageEnumMap = {
  ApplicationStage.applied: 'applied',
  ApplicationStage.shortlisted: 'shortlisted',
  ApplicationStage.interview: 'interview',
  ApplicationStage.offer: 'offer',
  ApplicationStage.hired: 'hired',
  ApplicationStage.rejected: 'rejected',
  ApplicationStage.unknown: 'unknown',
};

ApplicantsOfJobPageDto _$ApplicantsOfJobPageDtoFromJson(
        Map<String, dynamic> json) =>
    ApplicantsOfJobPageDto(
      items: (json['items'] as List<dynamic>)
          .map((e) => ApplicantOfJobDto.fromJson(e as Map<String, dynamic>))
          .toList(),
      nextCursor: json['next_cursor'] as String?,
    );

Map<String, dynamic> _$ApplicantsOfJobPageDtoToJson(
        ApplicantsOfJobPageDto instance) =>
    <String, dynamic>{
      'items': instance.items.map((e) => e.toJson()).toList(),
      'next_cursor': instance.nextCursor,
    };
