import 'package:jobify_app/data/preferences/desired_role.dart';

/// Request body for PATCH /v1/applicants/me/preferences. Only non-null
/// fields the caller actually set should be included — callers build this
/// with just the fields they're changing (unlike ProfileUpdateDto, this is
/// NOT a full-form-always-sends-every-key DTO, since PreferencesScreen and
/// EditProfileScreen both partially update this resource).
///
/// toJson() is hand-written, not code-generated: `@JsonSerializable(
/// includeIfNull: false)` on this project's installed json_serializable +
/// Dart SDK combination emits generated code using the "null-aware
/// elements" collection-literal syntax (`'key': ?value`), which this
/// project's declared language version (pubspec.yaml `sdk: ^3.6.0`) does
/// not support — build_runner fails with a FormatterException. A
/// hand-written toJson() avoids the codegen path entirely while keeping
/// the same partial-update behavior.
class PreferencesUpdateDto {
  const PreferencesUpdateDto({
    this.desiredRole,
    this.locations,
    this.expectedCtc,
  });

  final DesiredRole? desiredRole;
  final List<String>? locations;
  final num? expectedCtc;

  Map<String, dynamic> toJson() => {
        if (desiredRole != null) 'desired_role': desiredRole!.wireValue,
        if (locations != null) 'locations': locations,
        if (expectedCtc != null) 'expected_ctc': expectedCtc,
      };
}
