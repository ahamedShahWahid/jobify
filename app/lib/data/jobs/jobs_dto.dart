import 'package:freezed_annotation/freezed_annotation.dart';

import 'package:kpa_app/data/feed/feed_dto.dart';

part 'jobs_dto.freezed.dart';
part 'jobs_dto.g.dart';

@freezed
abstract class JobDetailDto with _$JobDetailDto {
  const factory JobDetailDto({
    required JobSummaryDto job,
    required EmployerSummaryDto employer,
    MatchSummaryDto? match,
    ApplicationDto? application,
    SavedJobDto? savedJob,
  }) = _JobDetailDto;

  factory JobDetailDto.fromJson(Map<String, dynamic> json) =>
      _$JobDetailDtoFromJson(json);
}

@freezed
abstract class ApplicationDto with _$ApplicationDto {
  const factory ApplicationDto({
    required String id,
    required String applicantId,
    required String jobId,
    required String status,
    required String source,
    required DateTime createdAt,
    DateTime? withdrawnAt,
  }) = _ApplicationDto;

  factory ApplicationDto.fromJson(Map<String, dynamic> json) =>
      _$ApplicationDtoFromJson(json);
}

@freezed
abstract class SavedJobDto with _$SavedJobDto {
  const factory SavedJobDto({
    required String id,
    required String applicantId,
    required String jobId,
    required DateTime createdAt,
  }) = _SavedJobDto;

  factory SavedJobDto.fromJson(Map<String, dynamic> json) =>
      _$SavedJobDtoFromJson(json);
}

@freezed
abstract class ApplicationsPageDto with _$ApplicationsPageDto {
  const factory ApplicationsPageDto({
    required List<ApplicationListItemDto> items,
    String? nextCursor,
  }) = _ApplicationsPageDto;

  factory ApplicationsPageDto.fromJson(Map<String, dynamic> json) =>
      _$ApplicationsPageDtoFromJson(json);
}

@freezed
abstract class ApplicationListItemDto with _$ApplicationListItemDto {
  const factory ApplicationListItemDto({
    required ApplicationDto application,
    required JobSummaryDto job,
    required EmployerSummaryDto employer,
  }) = _ApplicationListItemDto;

  factory ApplicationListItemDto.fromJson(Map<String, dynamic> json) =>
      _$ApplicationListItemDtoFromJson(json);
}

@freezed
abstract class SavedJobsPageDto with _$SavedJobsPageDto {
  const factory SavedJobsPageDto({
    required List<SavedJobListItemDto> items,
    String? nextCursor,
  }) = _SavedJobsPageDto;

  factory SavedJobsPageDto.fromJson(Map<String, dynamic> json) =>
      _$SavedJobsPageDtoFromJson(json);
}

@freezed
abstract class SavedJobListItemDto with _$SavedJobListItemDto {
  const factory SavedJobListItemDto({
    required SavedJobDto saved,
    required JobSummaryDto job,
    required EmployerSummaryDto employer,
    MatchSummaryDto? match,
  }) = _SavedJobListItemDto;

  factory SavedJobListItemDto.fromJson(Map<String, dynamic> json) =>
      _$SavedJobListItemDtoFromJson(json);
}
