// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'recruiter_job_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

RecruiterJobDto _$RecruiterJobDtoFromJson(Map<String, dynamic> json) =>
    RecruiterJobDto(
      id: json['id'] as String,
      title: json['title'] as String,
      description: json['description'] as String,
      locations:
          (json['locations'] as List<dynamic>).map((e) => e as String).toList(),
      minExpYears: (json['min_exp_years'] as num).toInt(),
      maxExpYears: (json['max_exp_years'] as num).toInt(),
      status: json['status'] as String,
      postedAt: DateTime.parse(json['posted_at'] as String),
      employerVerified: json['employer_verified'] as bool,
      ctcMin: (json['ctc_min'] as num?)?.toDouble(),
      ctcMax: (json['ctc_max'] as num?)?.toDouble(),
      applicantCount: (json['applicant_count'] as num?)?.toInt() ?? 0,
      surfacedMatchCount: (json['surfaced_match_count'] as num?)?.toInt() ?? 0,
    );

Map<String, dynamic> _$RecruiterJobDtoToJson(RecruiterJobDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'title': instance.title,
      'description': instance.description,
      'locations': instance.locations,
      'min_exp_years': instance.minExpYears,
      'max_exp_years': instance.maxExpYears,
      'ctc_min': instance.ctcMin,
      'ctc_max': instance.ctcMax,
      'status': instance.status,
      'posted_at': instance.postedAt.toIso8601String(),
      'employer_verified': instance.employerVerified,
      'applicant_count': instance.applicantCount,
      'surfaced_match_count': instance.surfacedMatchCount,
    };

RecruiterJobsPageDto _$RecruiterJobsPageDtoFromJson(
        Map<String, dynamic> json) =>
    RecruiterJobsPageDto(
      items: (json['items'] as List<dynamic>)
          .map((e) => RecruiterJobDto.fromJson(e as Map<String, dynamic>))
          .toList(),
      nextCursor: json['next_cursor'] as String?,
    );

Map<String, dynamic> _$RecruiterJobsPageDtoToJson(
        RecruiterJobsPageDto instance) =>
    <String, dynamic>{
      'items': instance.items.map((e) => e.toJson()).toList(),
      'next_cursor': instance.nextCursor,
    };
