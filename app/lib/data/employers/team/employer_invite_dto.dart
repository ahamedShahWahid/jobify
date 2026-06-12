import 'package:json_annotation/json_annotation.dart';

part 'employer_invite_dto.g.dart';

/// Mirrors InviteRead (api/src/jobify/routes/employers.py) — an owner's view of a
/// pending invite under GET/POST /v1/employers/{id}/invites.
@JsonSerializable()
class InviteDto {
  const InviteDto({
    required this.id,
    required this.employerId,
    required this.email,
    required this.role,
    required this.status,
    required this.expiresAt,
    required this.createdAt,
    this.invitedByUserId,
  });

  factory InviteDto.fromJson(Map<String, dynamic> json) =>
      _$InviteDtoFromJson(json);

  final String id;

  @JsonKey(name: 'employer_id')
  final String employerId;

  final String email;
  final String role;
  final String status;

  @JsonKey(name: 'expires_at')
  final DateTime expiresAt;

  @JsonKey(name: 'created_at')
  final DateTime createdAt;

  @JsonKey(name: 'invited_by_user_id')
  final String? invitedByUserId;

  Map<String, dynamic> toJson() => _$InviteDtoToJson(this);
}

/// Mirrors MyInviteRead (api/src/jobify/routes/invites.py) — the invitee's view of
/// a pending invite under GET /v1/me/invites.
@JsonSerializable()
class MyInviteDto {
  const MyInviteDto({
    required this.id,
    required this.employerId,
    required this.employerName,
    required this.role,
    required this.expiresAt,
    required this.createdAt,
  });

  factory MyInviteDto.fromJson(Map<String, dynamic> json) =>
      _$MyInviteDtoFromJson(json);

  final String id;

  @JsonKey(name: 'employer_id')
  final String employerId;

  @JsonKey(name: 'employer_name')
  final String employerName;

  final String role;

  @JsonKey(name: 'expires_at')
  final DateTime expiresAt;

  @JsonKey(name: 'created_at')
  final DateTime createdAt;

  Map<String, dynamic> toJson() => _$MyInviteDtoToJson(this);
}

/// Mirrors AcceptResult (api/src/jobify/routes/invites.py) — accept/decline reply.
@JsonSerializable()
class AcceptResultDto {
  const AcceptResultDto({
    required this.employerId,
    required this.role,
    required this.status,
  });

  factory AcceptResultDto.fromJson(Map<String, dynamic> json) =>
      _$AcceptResultDtoFromJson(json);

  @JsonKey(name: 'employer_id')
  final String employerId;

  final String role;
  final String status;

  Map<String, dynamic> toJson() => _$AcceptResultDtoToJson(this);
}
