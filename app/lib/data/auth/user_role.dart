import 'package:json_annotation/json_annotation.dart';

part 'user_role.g.dart';

/// Mirrors the backend UserRole StrEnum (api/src/kpa/db/models.py:UserRole).
/// `unknown` is the forward-compat sentinel for a wire value this client
/// does not yet know about — never sent, only parsed.
@JsonEnum(alwaysCreate: true)
enum UserRole {
  @JsonValue('applicant')
  applicant,
  @JsonValue('recruiter')
  recruiter,
  @JsonValue('admin')
  admin,
  @JsonValue('unknown')
  unknown;

  /// Parse a wire string; anything unrecognized → [UserRole.unknown].
  static UserRole fromWire(String raw) => switch (raw) {
        'applicant' => UserRole.applicant,
        'recruiter' => UserRole.recruiter,
        'admin' => UserRole.admin,
        _ => UserRole.unknown,
      };

  /// True for roles that use the recruiter shell (recruiter + admin).
  bool get usesRecruiterShell =>
      this == UserRole.recruiter || this == UserRole.admin;
}
