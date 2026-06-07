// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'member_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

MemberDto _$MemberDtoFromJson(Map<String, dynamic> json) => MemberDto(
      userId: json['user_id'] as String,
      role: json['role'] as String,
      addedAt: DateTime.parse(json['added_at'] as String),
      email: json['email'] as String?,
      displayName: json['display_name'] as String?,
    );

Map<String, dynamic> _$MemberDtoToJson(MemberDto instance) => <String, dynamic>{
      'user_id': instance.userId,
      'email': instance.email,
      'display_name': instance.displayName,
      'role': instance.role,
      'added_at': instance.addedAt.toIso8601String(),
    };
