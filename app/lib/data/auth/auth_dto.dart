import 'package:freezed_annotation/freezed_annotation.dart';

part 'auth_dto.freezed.dart';
part 'auth_dto.g.dart';

@freezed
abstract class SignInResponseDto with _$SignInResponseDto {
  const factory SignInResponseDto({
    required String access,
    required String refresh,
    required AuthUserDto user,
    AuthApplicantDto? applicant,
  }) = _SignInResponseDto;

  factory SignInResponseDto.fromJson(Map<String, dynamic> json) =>
      _$SignInResponseDtoFromJson(json);
}

@freezed
abstract class RefreshResponseDto with _$RefreshResponseDto {
  const factory RefreshResponseDto({
    required String access,
    required String refresh,
  }) = _RefreshResponseDto;

  factory RefreshResponseDto.fromJson(Map<String, dynamic> json) =>
      _$RefreshResponseDtoFromJson(json);
}

@freezed
abstract class AuthUserDto with _$AuthUserDto {
  const factory AuthUserDto({
    required String id,
    required String email,
    required String role,
    String? displayName,
  }) = _AuthUserDto;

  factory AuthUserDto.fromJson(Map<String, dynamic> json) =>
      _$AuthUserDtoFromJson(json);
}

@freezed
abstract class AuthApplicantDto with _$AuthApplicantDto {
  const factory AuthApplicantDto({
    required String id,
    required String userId,
  }) = _AuthApplicantDto;

  factory AuthApplicantDto.fromJson(Map<String, dynamic> json) =>
      _$AuthApplicantDtoFromJson(json);
}
