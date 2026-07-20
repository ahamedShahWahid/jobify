// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'jobs_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

ApplicationDto _$ApplicationDtoFromJson(Map<String, dynamic> json) =>
    ApplicationDto(
      id: json['id'] as String,
      jobId: json['job_id'] as String,
      status: $enumDecode(_$ApplicationStatusEnumMap, json['status'],
          unknownValue: ApplicationStatus.unknown),
      source: $enumDecode(_$ApplicationSourceEnumMap, json['source'],
          unknownValue: ApplicationSource.unknown),
      stage: $enumDecode(_$ApplicationStageEnumMap, json['stage'],
          unknownValue: ApplicationStage.unknown),
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );

Map<String, dynamic> _$ApplicationDtoToJson(ApplicationDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'job_id': instance.jobId,
      'status': _$ApplicationStatusEnumMap[instance.status]!,
      'source': _$ApplicationSourceEnumMap[instance.source]!,
      'stage': _$ApplicationStageEnumMap[instance.stage]!,
      'created_at': instance.createdAt.toIso8601String(),
      'updated_at': instance.updatedAt.toIso8601String(),
    };

const _$ApplicationStatusEnumMap = {
  ApplicationStatus.applied: 'applied',
  ApplicationStatus.withdrawn: 'withdrawn',
  ApplicationStatus.unknown: 'unknown',
};

const _$ApplicationSourceEnumMap = {
  ApplicationSource.feed: 'feed',
  ApplicationSource.detail: 'detail',
  ApplicationSource.unknown: 'unknown',
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

SavedJobDto _$SavedJobDtoFromJson(Map<String, dynamic> json) => SavedJobDto(
      id: json['id'] as String,
      jobId: json['job_id'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
    );

Map<String, dynamic> _$SavedJobDtoToJson(SavedJobDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'job_id': instance.jobId,
      'created_at': instance.createdAt.toIso8601String(),
    };

ApplicationsPageDto _$ApplicationsPageDtoFromJson(Map<String, dynamic> json) =>
    ApplicationsPageDto(
      items: (json['items'] as List<dynamic>)
          .map(
              (e) => ApplicationListItemDto.fromJson(e as Map<String, dynamic>))
          .toList(),
      nextCursor: json['next_cursor'] as String?,
    );

Map<String, dynamic> _$ApplicationsPageDtoToJson(
        ApplicationsPageDto instance) =>
    <String, dynamic>{
      'items': instance.items.map((e) => e.toJson()).toList(),
      'next_cursor': instance.nextCursor,
    };

ApplicationListItemDto _$ApplicationListItemDtoFromJson(
        Map<String, dynamic> json) =>
    ApplicationListItemDto(
      application:
          ApplicationDto.fromJson(json['application'] as Map<String, dynamic>),
      job: JobSummaryDto.fromJson(json['job'] as Map<String, dynamic>),
      employer:
          EmployerSummaryDto.fromJson(json['employer'] as Map<String, dynamic>),
    );

Map<String, dynamic> _$ApplicationListItemDtoToJson(
        ApplicationListItemDto instance) =>
    <String, dynamic>{
      'application': instance.application.toJson(),
      'job': instance.job.toJson(),
      'employer': instance.employer.toJson(),
    };

SavedJobsPageDto _$SavedJobsPageDtoFromJson(Map<String, dynamic> json) =>
    SavedJobsPageDto(
      items: (json['items'] as List<dynamic>)
          .map((e) => SavedJobListItemDto.fromJson(e as Map<String, dynamic>))
          .toList(),
      nextCursor: json['next_cursor'] as String?,
    );

Map<String, dynamic> _$SavedJobsPageDtoToJson(SavedJobsPageDto instance) =>
    <String, dynamic>{
      'items': instance.items.map((e) => e.toJson()).toList(),
      'next_cursor': instance.nextCursor,
    };

SavedJobListItemDto _$SavedJobListItemDtoFromJson(Map<String, dynamic> json) =>
    SavedJobListItemDto(
      saved: SavedJobDto.fromJson(json['saved_job'] as Map<String, dynamic>),
      job: JobSummaryDto.fromJson(json['job'] as Map<String, dynamic>),
      employer:
          EmployerSummaryDto.fromJson(json['employer'] as Map<String, dynamic>),
      match: json['match'] == null
          ? null
          : MatchSummaryDto.fromJson(json['match'] as Map<String, dynamic>),
    );

Map<String, dynamic> _$SavedJobListItemDtoToJson(
        SavedJobListItemDto instance) =>
    <String, dynamic>{
      'saved_job': instance.saved.toJson(),
      'job': instance.job.toJson(),
      'employer': instance.employer.toJson(),
      'match': instance.match?.toJson(),
    };

StageEventDto _$StageEventDtoFromJson(Map<String, dynamic> json) =>
    StageEventDto(
      fromStage: $enumDecode(_$ApplicationStageEnumMap, json['from_stage'],
          unknownValue: ApplicationStage.unknown),
      toStage: $enumDecode(_$ApplicationStageEnumMap, json['to_stage'],
          unknownValue: ApplicationStage.unknown),
      createdAt: DateTime.parse(json['created_at'] as String),
    );

Map<String, dynamic> _$StageEventDtoToJson(StageEventDto instance) =>
    <String, dynamic>{
      'from_stage': _$ApplicationStageEnumMap[instance.fromStage]!,
      'to_stage': _$ApplicationStageEnumMap[instance.toStage]!,
      'created_at': instance.createdAt.toIso8601String(),
    };

ApplicationTimelineDto _$ApplicationTimelineDtoFromJson(
        Map<String, dynamic> json) =>
    ApplicationTimelineDto(
      items: (json['items'] as List<dynamic>)
          .map((e) => StageEventDto.fromJson(e as Map<String, dynamic>))
          .toList(),
    );

Map<String, dynamic> _$ApplicationTimelineDtoToJson(
        ApplicationTimelineDto instance) =>
    <String, dynamic>{
      'items': instance.items.map((e) => e.toJson()).toList(),
    };

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
