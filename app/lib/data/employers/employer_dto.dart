import 'package:json_annotation/json_annotation.dart';

part 'employer_dto.g.dart';

/// Mirrors EmployerRead (api/src/kpa/routes/employers.py).
@JsonSerializable()
class EmployerDto {
  const EmployerDto({
    required this.id,
    required this.name,
    required this.createdAt,
    this.gst,
    this.verifiedAt,
  });

  factory EmployerDto.fromJson(Map<String, dynamic> json) =>
      _$EmployerDtoFromJson(json);

  final String id;
  final String name;
  final String? gst;

  @JsonKey(name: 'verified_at')
  final DateTime? verifiedAt;

  @JsonKey(name: 'created_at')
  final DateTime createdAt;

  bool get isVerified => verifiedAt != null;

  Map<String, dynamic> toJson() => _$EmployerDtoToJson(this);
}
