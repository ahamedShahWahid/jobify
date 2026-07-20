import 'package:freezed_annotation/freezed_annotation.dart';

import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/jobs/application_source.dart';
import 'package:jobify_app/data/jobs/application_stage.dart';
import 'package:jobify_app/data/jobs/application_status.dart';

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

@JsonSerializable()
class ApplicationDto {
  const ApplicationDto({
    required this.id,
    required this.jobId,
    required this.status,
    required this.source,
    required this.stage,
    required this.createdAt,
    required this.updatedAt,
  });

  factory ApplicationDto.fromJson(Map<String, dynamic> json) =>
      _$ApplicationDtoFromJson(json);

  final String id;
  final String jobId;
  @JsonKey(unknownEnumValue: ApplicationStatus.unknown)
  final ApplicationStatus status;
  @JsonKey(unknownEnumValue: ApplicationSource.unknown)
  final ApplicationSource source;
  @JsonKey(unknownEnumValue: ApplicationStage.unknown)
  final ApplicationStage stage;
  final DateTime createdAt;
  // Backend ApplicationRead sends `updated_at` (not `applicant_id` or a
  // dedicated `withdrawn_at`); for a withdrawn row this is the withdrawal time.
  final DateTime updatedAt;

  Map<String, dynamic> toJson() => _$ApplicationDtoToJson(this);
}

@JsonSerializable()
class SavedJobDto {
  const SavedJobDto({
    required this.id,
    required this.jobId,
    required this.createdAt,
  });

  factory SavedJobDto.fromJson(Map<String, dynamic> json) =>
      _$SavedJobDtoFromJson(json);

  final String id;
  final String jobId;
  final DateTime createdAt;

  Map<String, dynamic> toJson() => _$SavedJobDtoToJson(this);
}

@JsonSerializable()
class ApplicationsPageDto {
  const ApplicationsPageDto({
    required this.items,
    this.nextCursor,
  });

  factory ApplicationsPageDto.fromJson(Map<String, dynamic> json) =>
      _$ApplicationsPageDtoFromJson(json);

  final List<ApplicationListItemDto> items;
  final String? nextCursor;

  Map<String, dynamic> toJson() => _$ApplicationsPageDtoToJson(this);
}

@JsonSerializable()
class ApplicationListItemDto {
  const ApplicationListItemDto({
    required this.application,
    required this.job,
    required this.employer,
  });

  factory ApplicationListItemDto.fromJson(Map<String, dynamic> json) =>
      _$ApplicationListItemDtoFromJson(json);

  final ApplicationDto application;
  final JobSummaryDto job;
  final EmployerSummaryDto employer;

  Map<String, dynamic> toJson() => _$ApplicationListItemDtoToJson(this);
}

@JsonSerializable()
class SavedJobsPageDto {
  const SavedJobsPageDto({
    required this.items,
    this.nextCursor,
  });

  factory SavedJobsPageDto.fromJson(Map<String, dynamic> json) =>
      _$SavedJobsPageDtoFromJson(json);

  final List<SavedJobListItemDto> items;
  final String? nextCursor;

  Map<String, dynamic> toJson() => _$SavedJobsPageDtoToJson(this);
}

@JsonSerializable()
class SavedJobListItemDto {
  const SavedJobListItemDto({
    required this.saved,
    required this.job,
    required this.employer,
    this.match,
  });

  factory SavedJobListItemDto.fromJson(Map<String, dynamic> json) =>
      _$SavedJobListItemDtoFromJson(json);

  // Backend SavedJobListItem wraps the saved row under `saved_job`.
  @JsonKey(name: 'saved_job')
  final SavedJobDto saved;
  final JobSummaryDto job;
  final EmployerSummaryDto employer;
  // Backend does not include a match on the saved-list shape; always null.
  final MatchSummaryDto? match;

  Map<String, dynamic> toJson() => _$SavedJobListItemDtoToJson(this);
}

@JsonSerializable()
class StageEventDto {
  const StageEventDto({
    required this.fromStage,
    required this.toStage,
    required this.createdAt,
  });

  factory StageEventDto.fromJson(Map<String, dynamic> json) =>
      _$StageEventDtoFromJson(json);

  @JsonKey(unknownEnumValue: ApplicationStage.unknown)
  final ApplicationStage fromStage;
  @JsonKey(unknownEnumValue: ApplicationStage.unknown)
  final ApplicationStage toStage;
  final DateTime createdAt;

  Map<String, dynamic> toJson() => _$StageEventDtoToJson(this);
}

@JsonSerializable()
class ApplicationTimelineDto {
  const ApplicationTimelineDto({required this.items});

  factory ApplicationTimelineDto.fromJson(Map<String, dynamic> json) =>
      _$ApplicationTimelineDtoFromJson(json);

  final List<StageEventDto> items;

  Map<String, dynamic> toJson() => _$ApplicationTimelineDtoToJson(this);
}
