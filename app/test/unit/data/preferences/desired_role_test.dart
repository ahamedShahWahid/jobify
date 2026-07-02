import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/preferences/desired_role.dart';
import 'package:jobify_app/data/preferences/preferences_dto.dart';

void main() {
  test(
      'every real role round-trips: wireValue parses back to the same enum '
      '(pins the hand-maintained @JsonValue and wireValue maps together)', () {
    for (final role in DesiredRole.values) {
      if (role == DesiredRole.unknown) continue;
      final dto = PreferencesDto.fromJson({
        'desired_role': role.wireValue,
        'locations': <String>[],
        'expected_ctc': null,
      });
      expect(dto.desiredRole, role, reason: 'round-trip failed for $role');
    }
  });

  test('an unrecognised wire string parses to DesiredRole.unknown', () {
    final dto = PreferencesDto.fromJson({
      'desired_role': 'underwater_basket_weaving',
      'locations': <String>[],
      'expected_ctc': null,
    });
    expect(dto.desiredRole, DesiredRole.unknown);
  });

  test('DesiredRole.unknown.wireValue throws StateError', () {
    expect(() => DesiredRole.unknown.wireValue, throwsStateError);
  });
}
