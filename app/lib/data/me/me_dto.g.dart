// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'me_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

MeDto _$MeDtoFromJson(Map<String, dynamic> json) => MeDto(
      id: json['id'] as String,
      email: json['email'] as String?,
      role: json['role'] as String,
      displayName: json['display_name'] as String?,
      applicant: json['applicant'] == null
          ? null
          : ApplicantSummaryDto.fromJson(
              json['applicant'] as Map<String, dynamic>),
    );

Map<String, dynamic> _$MeDtoToJson(MeDto instance) => <String, dynamic>{
      'id': instance.id,
      'email': instance.email,
      'role': instance.role,
      'display_name': instance.displayName,
      'applicant': instance.applicant?.toJson(),
    };

ApplicantSummaryDto _$ApplicantSummaryDtoFromJson(Map<String, dynamic> json) =>
    ApplicantSummaryDto(
      id: json['id'] as String,
      fullName: json['full_name'] as String?,
      locations: (json['locations'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          const [],
      noticePeriodDays: (json['notice_period_days'] as num?)?.toInt(),
      currentCtc: json['current_ctc'] as String?,
      expectedCtc: json['expected_ctc'] as String?,
      yearsExperience: json['years_experience'] as String?,
    );

Map<String, dynamic> _$ApplicantSummaryDtoToJson(
        ApplicantSummaryDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'full_name': instance.fullName,
      'locations': instance.locations,
      'notice_period_days': instance.noticePeriodDays,
      'current_ctc': instance.currentCtc,
      'expected_ctc': instance.expectedCtc,
      'years_experience': instance.yearsExperience,
    };
