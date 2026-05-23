import 'package:freezed_annotation/freezed_annotation.dart';

part 'me_dto.freezed.dart';
part 'me_dto.g.dart';

@freezed
abstract class MeDto with _$MeDto {
  const factory MeDto({
    required MeUserDto user,
    ApplicantSummaryDto? applicant,
  }) = _MeDto;

  factory MeDto.fromJson(Map<String, dynamic> json) => _$MeDtoFromJson(json);
}

@freezed
abstract class MeUserDto with _$MeUserDto {
  const factory MeUserDto({
    required String id,
    required String email,
    required String role,
    required DateTime createdAt,
    String? displayName,
  }) = _MeUserDto;

  factory MeUserDto.fromJson(Map<String, dynamic> json) =>
      _$MeUserDtoFromJson(json);
}

@freezed
abstract class ApplicantSummaryDto with _$ApplicantSummaryDto {
  const factory ApplicantSummaryDto({
    required String id,
    required String userId,
  }) = _ApplicantSummaryDto;

  factory ApplicantSummaryDto.fromJson(Map<String, dynamic> json) =>
      _$ApplicantSummaryDtoFromJson(json);
}
