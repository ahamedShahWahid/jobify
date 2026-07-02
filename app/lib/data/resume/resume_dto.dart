import 'package:jobify_app/data/resume/resume_parse_status.dart';
import 'package:json_annotation/json_annotation.dart';

part 'resume_dto.g.dart';

/// Mirrors api `ResumeRead` (routes/resumes.py).
@JsonSerializable(createToJson: false)
class ResumeDto {
  const ResumeDto({
    required this.id,
    required this.applicantId,
    required this.originalFilename,
    required this.contentType,
    required this.sizeBytes,
    required this.parseStatus,
    this.parsedJson,
    required this.createdAt,
  });

  factory ResumeDto.fromJson(Map<String, dynamic> json) =>
      _$ResumeDtoFromJson(json);

  final String id;
  @JsonKey(name: 'applicant_id')
  final String applicantId;
  @JsonKey(name: 'original_filename')
  final String originalFilename;
  @JsonKey(name: 'content_type')
  final String contentType;
  @JsonKey(name: 'size_bytes')
  final int sizeBytes;
  @JsonKey(name: 'parse_status', unknownEnumValue: ResumeParseStatus.unknown)
  final ResumeParseStatus parseStatus;
  @JsonKey(name: 'parsed_json')
  final Map<String, dynamic>? parsedJson;
  @JsonKey(name: 'created_at')
  final DateTime createdAt;
}
