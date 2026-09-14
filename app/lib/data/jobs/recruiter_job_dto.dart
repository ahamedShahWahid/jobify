import 'package:json_annotation/json_annotation.dart';

part 'recruiter_job_dto.g.dart';

/// Mirrors the backend's flat RecruiterJobRow (= JobSummaryRead + applicant/
/// match counts) for GET /v1/jobs/me, and plain JobRead for
/// GET /v1/jobs/me/{id}, POST /v1/jobs, and PATCH /v1/jobs/{id}.
///
/// `description` is nullable: list rows from GET /v1/jobs/me omit it
/// entirely (PERF-09 — it's the largest field on a job and unused by any
/// list/card view). Only GET /v1/jobs/me/{id} (and the create/patch
/// responses) carry it. Opening the edit form must always go through
/// RecruiterJobsRepository.getJob(id) — see EditJobResolver — never prefill
/// from a list row directly. The @JsonKey(defaultValue:) count fields
/// handle the reverse gap: POST/PATCH responses have no counts.
@JsonSerializable()
class RecruiterJobDto {
  const RecruiterJobDto({
    required this.id,
    required this.title,
    required this.locations,
    required this.minExpYears,
    required this.maxExpYears,
    required this.status,
    required this.postedAt,
    required this.employerVerified,
    this.description,
    this.ctcMin,
    this.ctcMax,
    this.applicantCount = 0,
    this.surfacedMatchCount = 0,
  });

  factory RecruiterJobDto.fromJson(Map<String, dynamic> json) =>
      _$RecruiterJobDtoFromJson(json);

  final String id;
  final String title;
  final String? description;
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
  const RecruiterJobsPageDto({required this.items, this.nextCursor});

  factory RecruiterJobsPageDto.fromJson(Map<String, dynamic> json) =>
      _$RecruiterJobsPageDtoFromJson(json);

  final List<RecruiterJobDto> items;

  @JsonKey(name: 'next_cursor')
  final String? nextCursor;

  Map<String, dynamic> toJson() => _$RecruiterJobsPageDtoToJson(this);
}
