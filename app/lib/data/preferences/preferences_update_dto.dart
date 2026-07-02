import 'package:jobify_app/data/preferences/desired_role.dart';

/// Request body for PATCH /v1/applicants/me/preferences. This is a FULL-FORM
/// DTO: both callers (PreferencesScreen, EditProfileScreen) are full-form
/// editors, so every field is always sent — an explicit `null` CLEARS
/// `desired_role`/`expected_ctc` on the server, and an empty `locations`
/// list clears locations (the key is non-nullable on the wire). The one
/// exception is `desiredRole == DesiredRole.unknown` (the server sent a role
/// this app build doesn't recognise): the key is OMITTED so saving preserves
/// the server value instead of clearing it.
///
/// toJson() is hand-written, not code-generated: `@JsonSerializable(
/// includeIfNull: false)` on this project's installed json_serializable +
/// Dart SDK combination emits generated code using the "null-aware
/// elements" collection-literal syntax (`'key': ?value`), which this
/// project's declared language version (pubspec.yaml `sdk: ^3.6.0`) does
/// not support — build_runner fails with a FormatterException. A
/// hand-written toJson() avoids the codegen path entirely.
class PreferencesUpdateDto {
  const PreferencesUpdateDto({
    required this.desiredRole,
    required this.locations,
    required this.expectedCtc,
  });

  /// null = clear; unknown = preserve server value (key omitted).
  final DesiredRole? desiredRole;

  /// empty = clear.
  final List<String> locations;

  /// null = clear.
  final num? expectedCtc;

  Map<String, dynamic> toJson() => {
        // `unknown` = the server sent a role this app build doesn't know;
        // omit the key so saving preserves it (an explicit null would
        // CLEAR it).
        if (desiredRole != DesiredRole.unknown)
          'desired_role': desiredRole?.wireValue,
        'locations': locations,
        'expected_ctc': expectedCtc,
      };
}
