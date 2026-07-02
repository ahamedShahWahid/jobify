import 'package:json_annotation/json_annotation.dart';

part 'profile_update_dto.g.dart';

/// Request body for PATCH /v1/applicants/me. locations/expected_ctc moved
/// to PreferencesUpdateDto (PATCH /v1/applicants/me/preferences).
@JsonSerializable(createFactory: false, includeIfNull: true)
class ProfileUpdateDto {
  const ProfileUpdateDto({
    required this.fullName,
    this.noticePeriodDays,
    this.currentCtc,
    this.yearsExperience,
  });

  @JsonKey(name: 'full_name')
  final String fullName;
  // Sent as JSON numbers; the backend's Decimal fields coerce from number.
  @JsonKey(name: 'notice_period_days')
  final int? noticePeriodDays;
  @JsonKey(name: 'current_ctc')
  final num? currentCtc;
  @JsonKey(name: 'years_experience')
  final num? yearsExperience;

  Map<String, dynamic> toJson() => _$ProfileUpdateDtoToJson(this);
}
