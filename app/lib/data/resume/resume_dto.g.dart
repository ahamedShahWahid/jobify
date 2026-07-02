// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'resume_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

ResumeDto _$ResumeDtoFromJson(Map<String, dynamic> json) => ResumeDto(
      id: json['id'] as String,
      applicantId: json['applicant_id'] as String,
      originalFilename: json['original_filename'] as String,
      contentType: json['content_type'] as String,
      sizeBytes: (json['size_bytes'] as num).toInt(),
      parseStatus: $enumDecode(_$ResumeParseStatusEnumMap, json['parse_status'],
          unknownValue: ResumeParseStatus.unknown),
      parsedJson: json['parsed_json'] as Map<String, dynamic>?,
      createdAt: DateTime.parse(json['created_at'] as String),
    );

const _$ResumeParseStatusEnumMap = {
  ResumeParseStatus.pending: 'pending',
  ResumeParseStatus.parsing: 'parsing',
  ResumeParseStatus.parsed: 'parsed',
  ResumeParseStatus.failed: 'failed',
  ResumeParseStatus.unknown: 'unknown',
};
