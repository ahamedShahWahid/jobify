// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'employer_invite_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

InviteDto _$InviteDtoFromJson(Map<String, dynamic> json) => InviteDto(
      id: json['id'] as String,
      employerId: json['employer_id'] as String,
      email: json['email'] as String,
      role: json['role'] as String,
      status: json['status'] as String,
      expiresAt: DateTime.parse(json['expires_at'] as String),
      createdAt: DateTime.parse(json['created_at'] as String),
      invitedByUserId: json['invited_by_user_id'] as String?,
    );

Map<String, dynamic> _$InviteDtoToJson(InviteDto instance) => <String, dynamic>{
      'id': instance.id,
      'employer_id': instance.employerId,
      'email': instance.email,
      'role': instance.role,
      'status': instance.status,
      'expires_at': instance.expiresAt.toIso8601String(),
      'created_at': instance.createdAt.toIso8601String(),
      'invited_by_user_id': instance.invitedByUserId,
    };

MyInviteDto _$MyInviteDtoFromJson(Map<String, dynamic> json) => MyInviteDto(
      id: json['id'] as String,
      employerId: json['employer_id'] as String,
      employerName: json['employer_name'] as String,
      role: json['role'] as String,
      expiresAt: DateTime.parse(json['expires_at'] as String),
      createdAt: DateTime.parse(json['created_at'] as String),
    );

Map<String, dynamic> _$MyInviteDtoToJson(MyInviteDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'employer_id': instance.employerId,
      'employer_name': instance.employerName,
      'role': instance.role,
      'expires_at': instance.expiresAt.toIso8601String(),
      'created_at': instance.createdAt.toIso8601String(),
    };

AcceptResultDto _$AcceptResultDtoFromJson(Map<String, dynamic> json) =>
    AcceptResultDto(
      employerId: json['employer_id'] as String,
      role: json['role'] as String,
      status: json['status'] as String,
    );

Map<String, dynamic> _$AcceptResultDtoToJson(AcceptResultDto instance) =>
    <String, dynamic>{
      'employer_id': instance.employerId,
      'role': instance.role,
      'status': instance.status,
    };
