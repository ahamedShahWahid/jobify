// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'employer_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

EmployerDto _$EmployerDtoFromJson(Map<String, dynamic> json) => EmployerDto(
      id: json['id'] as String,
      name: json['name'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
      gst: json['gst'] as String?,
      verifiedAt: json['verified_at'] == null
          ? null
          : DateTime.parse(json['verified_at'] as String),
    );

Map<String, dynamic> _$EmployerDtoToJson(EmployerDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'name': instance.name,
      'gst': instance.gst,
      'verified_at': instance.verifiedAt?.toIso8601String(),
      'created_at': instance.createdAt.toIso8601String(),
    };
