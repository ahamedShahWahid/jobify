import 'package:json_annotation/json_annotation.dart';

part 'dsr_dto.g.dart';

@JsonSerializable()
class OwnerlessEmployerWarningDto {
  OwnerlessEmployerWarningDto({
    required this.type,
    required this.employerId,
    required this.employerName,
    required this.message,
  });

  factory OwnerlessEmployerWarningDto.fromJson(Map<String, dynamic> json) =>
      _$OwnerlessEmployerWarningDtoFromJson(json);

  final String type;
  @JsonKey(name: 'employer_id')
  final String employerId;
  @JsonKey(name: 'employer_name')
  final String employerName;
  final String message;
  Map<String, dynamic> toJson() => _$OwnerlessEmployerWarningDtoToJson(this);
}

@JsonSerializable()
class DsrDeleteResponse {
  DsrDeleteResponse({
    required this.deletedAt,
    required this.sectionCounts,
    required this.warnings,
  });

  factory DsrDeleteResponse.fromJson(Map<String, dynamic> json) =>
      _$DsrDeleteResponseFromJson(json);

  @JsonKey(name: 'deleted_at')
  final DateTime deletedAt;
  @JsonKey(name: 'section_counts')
  final Map<String, int> sectionCounts;
  final List<OwnerlessEmployerWarningDto> warnings;
}
