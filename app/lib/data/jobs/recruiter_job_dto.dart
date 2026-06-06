import 'package:json_annotation/json_annotation.dart';

part 'recruiter_job_dto.g.dart';

/// Mirrors the backend's flat RecruiterJobRow (= JobRead + applicant/match
/// counts). Used by GET /v1/jobs/me.
///
/// POST /v1/jobs and PATCH /v1/jobs/{id} return a plain JobRead WITHOUT the
/// two count fields. The @JsonKey(defaultValue:) annotations ensure those
/// responses also parse cleanly (missing keys → 0).
@JsonSerializable()
class RecruiterJobDto {
  const RecruiterJobDto({
    required this.id,
    required this.title,
    required this.description,
    required this.locations,
    required this.minExpYears,
    required this.maxExpYears,
    required this.status,
    required this.postedAt,
    required this.employerVerified,
    this.ctcMin,
    this.ctcMax,
    this.applicantCount = 0,
    this.surfacedMatchCount = 0,
  });

  factory RecruiterJobDto.fromJson(Map<String, dynamic> json) =>
      _$RecruiterJobDtoFromJson(json);

  final String id;
  final String title;
  final String description;
  final List<String> locations;

  @JsonKey(name: 'min_exp_years')
  final int minExpYears;

  @JsonKey(name: 'max_exp_years')
  final int maxExpYears;

  @JsonKey(name: 'ctc_min')
  final double? ctcMin;

  @JsonKey(name: 'ctc_max')
  final double? ctcMax;

  final String status;

  @JsonKey(name: 'posted_at')
  final DateTime postedAt;

  @JsonKey(name: 'employer_verified')
  final bool employerVerified;

  @JsonKey(name: 'applicant_count', defaultValue: 0)
  final int applicantCount;

  @JsonKey(name: 'surfaced_match_count', defaultValue: 0)
  final int surfacedMatchCount;

  Map<String, dynamic> toJson() => _$RecruiterJobDtoToJson(this);
}

/// Mirrors the paginated /v1/jobs/me response.
@JsonSerializable()
class RecruiterJobsPageDto {
  const RecruiterJobsPageDto({
    required this.items,
    this.nextCursor,
  });

  factory RecruiterJobsPageDto.fromJson(Map<String, dynamic> json) =>
      _$RecruiterJobsPageDtoFromJson(json);

  final List<RecruiterJobDto> items;

  @JsonKey(name: 'next_cursor')
  final String? nextCursor;

  Map<String, dynamic> toJson() => _$RecruiterJobsPageDtoToJson(this);
}
