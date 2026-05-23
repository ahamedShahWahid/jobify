// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'jobs_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_JobDetailDto _$JobDetailDtoFromJson(Map<String, dynamic> json) =>
    _JobDetailDto(
      job: JobSummaryDto.fromJson(json['job'] as Map<String, dynamic>),
      employer:
          EmployerSummaryDto.fromJson(json['employer'] as Map<String, dynamic>),
      match: json['match'] == null
          ? null
          : MatchSummaryDto.fromJson(json['match'] as Map<String, dynamic>),
      application: json['application'] == null
          ? null
          : ApplicationDto.fromJson(
              json['application'] as Map<String, dynamic>),
      savedJob: json['saved_job'] == null
          ? null
          : SavedJobDto.fromJson(json['saved_job'] as Map<String, dynamic>),
    );

Map<String, dynamic> _$JobDetailDtoToJson(_JobDetailDto instance) =>
    <String, dynamic>{
      'job': instance.job.toJson(),
      'employer': instance.employer.toJson(),
      'match': instance.match?.toJson(),
      'application': instance.application?.toJson(),
      'saved_job': instance.savedJob?.toJson(),
    };

_ApplicationDto _$ApplicationDtoFromJson(Map<String, dynamic> json) =>
    _ApplicationDto(
      id: json['id'] as String,
      applicantId: json['applicant_id'] as String,
      jobId: json['job_id'] as String,
      status: json['status'] as String,
      source: json['source'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
      withdrawnAt: json['withdrawn_at'] == null
          ? null
          : DateTime.parse(json['withdrawn_at'] as String),
    );

Map<String, dynamic> _$ApplicationDtoToJson(_ApplicationDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'applicant_id': instance.applicantId,
      'job_id': instance.jobId,
      'status': instance.status,
      'source': instance.source,
      'created_at': instance.createdAt.toIso8601String(),
      'withdrawn_at': instance.withdrawnAt?.toIso8601String(),
    };

_SavedJobDto _$SavedJobDtoFromJson(Map<String, dynamic> json) => _SavedJobDto(
      id: json['id'] as String,
      applicantId: json['applicant_id'] as String,
      jobId: json['job_id'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
    );

Map<String, dynamic> _$SavedJobDtoToJson(_SavedJobDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'applicant_id': instance.applicantId,
      'job_id': instance.jobId,
      'created_at': instance.createdAt.toIso8601String(),
    };

_ApplicationsPageDto _$ApplicationsPageDtoFromJson(Map<String, dynamic> json) =>
    _ApplicationsPageDto(
      items: (json['items'] as List<dynamic>)
          .map(
              (e) => ApplicationListItemDto.fromJson(e as Map<String, dynamic>))
          .toList(),
      nextCursor: json['next_cursor'] as String?,
    );

Map<String, dynamic> _$ApplicationsPageDtoToJson(
        _ApplicationsPageDto instance) =>
    <String, dynamic>{
      'items': instance.items.map((e) => e.toJson()).toList(),
      'next_cursor': instance.nextCursor,
    };

_ApplicationListItemDto _$ApplicationListItemDtoFromJson(
        Map<String, dynamic> json) =>
    _ApplicationListItemDto(
      application:
          ApplicationDto.fromJson(json['application'] as Map<String, dynamic>),
      job: JobSummaryDto.fromJson(json['job'] as Map<String, dynamic>),
      employer:
          EmployerSummaryDto.fromJson(json['employer'] as Map<String, dynamic>),
    );

Map<String, dynamic> _$ApplicationListItemDtoToJson(
        _ApplicationListItemDto instance) =>
    <String, dynamic>{
      'application': instance.application.toJson(),
      'job': instance.job.toJson(),
      'employer': instance.employer.toJson(),
    };

_SavedJobsPageDto _$SavedJobsPageDtoFromJson(Map<String, dynamic> json) =>
    _SavedJobsPageDto(
      items: (json['items'] as List<dynamic>)
          .map((e) => SavedJobListItemDto.fromJson(e as Map<String, dynamic>))
          .toList(),
      nextCursor: json['next_cursor'] as String?,
    );

Map<String, dynamic> _$SavedJobsPageDtoToJson(_SavedJobsPageDto instance) =>
    <String, dynamic>{
      'items': instance.items.map((e) => e.toJson()).toList(),
      'next_cursor': instance.nextCursor,
    };

_SavedJobListItemDto _$SavedJobListItemDtoFromJson(Map<String, dynamic> json) =>
    _SavedJobListItemDto(
      saved: SavedJobDto.fromJson(json['saved'] as Map<String, dynamic>),
      job: JobSummaryDto.fromJson(json['job'] as Map<String, dynamic>),
      employer:
          EmployerSummaryDto.fromJson(json['employer'] as Map<String, dynamic>),
      match: json['match'] == null
          ? null
          : MatchSummaryDto.fromJson(json['match'] as Map<String, dynamic>),
    );

Map<String, dynamic> _$SavedJobListItemDtoToJson(
        _SavedJobListItemDto instance) =>
    <String, dynamic>{
      'saved': instance.saved.toJson(),
      'job': instance.job.toJson(),
      'employer': instance.employer.toJson(),
      'match': instance.match?.toJson(),
    };
