import 'package:json_annotation/json_annotation.dart';

part 'applicant_of_job_dto.g.dart';

/// Mirrors one row of GET /v1/jobs/{id}/applicants.
@JsonSerializable()
class ApplicantOfJobDto {
  const ApplicantOfJobDto({
    required this.applicationId,
    required this.applicantId,
    required this.status,
    required this.appliedAt,
    this.displayName,
    this.email,
    this.matchScore,
    this.matchExplanation,
  });

  factory ApplicantOfJobDto.fromJson(Map<String, dynamic> json) =>
      _$ApplicantOfJobDtoFromJson(json);

  @JsonKey(name: 'application_id')
  final String applicationId;

  @JsonKey(name: 'applicant_id')
  final String applicantId;

  @JsonKey(name: 'display_name')
  final String? displayName;

  final String? email;
  final String status;

  @JsonKey(name: 'applied_at')
  final DateTime appliedAt;

  @JsonKey(name: 'match_score')
  final double? matchScore;

  @JsonKey(name: 'match_explanation')
  final Map<String, String>? matchExplanation;

  Map<String, dynamic> toJson() => _$ApplicantOfJobDtoToJson(this);
}

/// Mirrors the paginated GET /v1/jobs/{id}/applicants response.
@JsonSerializable()
class ApplicantsOfJobPageDto {
  const ApplicantsOfJobPageDto({
    required this.items,
    this.nextCursor,
  });

  factory ApplicantsOfJobPageDto.fromJson(Map<String, dynamic> json) =>
      _$ApplicantsOfJobPageDtoFromJson(json);

  final List<ApplicantOfJobDto> items;

  @JsonKey(name: 'next_cursor')
  final String? nextCursor;

  Map<String, dynamic> toJson() => _$ApplicantsOfJobPageDtoToJson(this);
}
