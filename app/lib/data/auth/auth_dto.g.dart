// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'auth_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_SignInResponseDto _$SignInResponseDtoFromJson(Map<String, dynamic> json) =>
    _SignInResponseDto(
      access: json['access'] as String,
      refresh: json['refresh'] as String,
      user: AuthUserDto.fromJson(json['user'] as Map<String, dynamic>),
      applicant: json['applicant'] == null
          ? null
          : AuthApplicantDto.fromJson(
              json['applicant'] as Map<String, dynamic>),
    );

Map<String, dynamic> _$SignInResponseDtoToJson(_SignInResponseDto instance) =>
    <String, dynamic>{
      'access': instance.access,
      'refresh': instance.refresh,
      'user': instance.user.toJson(),
      'applicant': instance.applicant?.toJson(),
    };

_RefreshResponseDto _$RefreshResponseDtoFromJson(Map<String, dynamic> json) =>
    _RefreshResponseDto(
      access: json['access'] as String,
      refresh: json['refresh'] as String,
    );

Map<String, dynamic> _$RefreshResponseDtoToJson(_RefreshResponseDto instance) =>
    <String, dynamic>{
      'access': instance.access,
      'refresh': instance.refresh,
    };

_AuthUserDto _$AuthUserDtoFromJson(Map<String, dynamic> json) => _AuthUserDto(
      id: json['id'] as String,
      email: json['email'] as String,
      role: json['role'] as String,
      displayName: json['display_name'] as String?,
    );

Map<String, dynamic> _$AuthUserDtoToJson(_AuthUserDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'email': instance.email,
      'role': instance.role,
      'display_name': instance.displayName,
    };

_AuthApplicantDto _$AuthApplicantDtoFromJson(Map<String, dynamic> json) =>
    _AuthApplicantDto(
      id: json['id'] as String,
      userId: json['user_id'] as String,
    );

Map<String, dynamic> _$AuthApplicantDtoToJson(_AuthApplicantDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'user_id': instance.userId,
    };
