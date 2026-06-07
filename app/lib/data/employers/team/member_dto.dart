import 'package:json_annotation/json_annotation.dart';

part 'member_dto.g.dart';

/// Mirrors MemberRead (api/src/kpa/routes/employers.py) — one row of
/// GET /v1/employers/{id}/members. `role` is 'owner' | 'member'.
@JsonSerializable()
class MemberDto {
  const MemberDto({
    required this.userId,
    required this.role,
    required this.addedAt,
    this.email,
    this.displayName,
  });

  factory MemberDto.fromJson(Map<String, dynamic> json) =>
      _$MemberDtoFromJson(json);

  @JsonKey(name: 'user_id')
  final String userId;

  final String? email;

  @JsonKey(name: 'display_name')
  final String? displayName;

  final String role;

  @JsonKey(name: 'added_at')
  final DateTime addedAt;

  bool get isOwner => role == 'owner';

  Map<String, dynamic> toJson() => _$MemberDtoToJson(this);
}
