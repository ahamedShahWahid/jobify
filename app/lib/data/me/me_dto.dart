import 'package:json_annotation/json_annotation.dart';

part 'me_dto.g.dart';

/// Mirrors the GET /v1/me response (api/src/kpa/routes/me.py: MeResponse).
/// The user fields are FLAT at the top level — there is no `user` wrapper —
/// and the role-shaped `applicant` is nested. Keep this in lockstep with the
/// backend; a drift surfaces as a "Something went wrong" screen on a 200 OK.
@JsonSerializable()
class MeDto {
  const MeDto({
    required this.id,
    required this.email,
    required this.role,
    this.displayName,
    this.applicant,
  });

  factory MeDto.fromJson(Map<String, dynamic> json) => _$MeDtoFromJson(json);

  final String id;

  // Nullable in lockstep with the backend: users.email is nullable in the DB
  // (phone-only auth later) and MeResponse.email is `str | None`.
  final String? email;

  final String role;

  // Not currently emitted by /v1/me; declared optional so the UI's
  // name-with-email-fallback works if the backend starts sending it.
  @JsonKey(name: 'display_name')
  final String? displayName;

  final ApplicantSummaryDto? applicant;

  Map<String, dynamic> toJson() => _$MeDtoToJson(this);
}

@JsonSerializable()
class ApplicantSummaryDto {
  const ApplicantSummaryDto({
    required this.id,
    required this.fullName,
    this.locations = const [],
    this.noticePeriodDays,
    this.currentCtc,
    this.expectedCtc,
    this.yearsExperience,
  });

  factory ApplicantSummaryDto.fromJson(Map<String, dynamic> json) =>
      _$ApplicantSummaryDtoFromJson(json);

  final String id;

  // Nullable in lockstep with the backend: migration 0015 made
  // applicants.full_name nullable (DSR scrubbing).
  @JsonKey(name: 'full_name')
  final String? fullName;

  final List<String> locations;

  @JsonKey(name: 'notice_period_days')
  final int? noticePeriodDays;

  // Pydantic v2 serializes Numeric/Decimal to a JSON *string* (e.g.
  // "1200000.50"), not a number — typing these as num would throw at parse.
  // Callers parse with double.tryParse(...) when they need a value.
  @JsonKey(name: 'current_ctc')
  final String? currentCtc;

  @JsonKey(name: 'expected_ctc')
  final String? expectedCtc;

  @JsonKey(name: 'years_experience')
  final String? yearsExperience;

  Map<String, dynamic> toJson() => _$ApplicantSummaryDtoToJson(this);
}
