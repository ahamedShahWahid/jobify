import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/preferences/desired_role.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';

void main() {
  test('toJson always contains all three keys for normal values', () {
    const dto = PreferencesUpdateDto(
      desiredRole: DesiredRole.softwareEngineering,
      locations: ['Pune'],
      expectedCtc: 1800000,
    );
    final json = dto.toJson();

    expect(json['desired_role'], 'software_engineering');
    expect(json['locations'], ['Pune']);
    expect(json['expected_ctc'], 1800000);
  });

  test('desiredRole: null → explicit desired_role: null (clears)', () {
    const dto = PreferencesUpdateDto(
      desiredRole: null,
      locations: ['Pune'],
      expectedCtc: 1,
    );
    final json = dto.toJson();

    expect(json.containsKey('desired_role'), isTrue);
    expect(json['desired_role'], isNull);
  });

  test('desiredRole: unknown → desired_role key ABSENT (preserves server)', () {
    const dto = PreferencesUpdateDto(
      desiredRole: DesiredRole.unknown,
      locations: ['Pune'],
      expectedCtc: 1,
    );
    expect(dto.toJson().containsKey('desired_role'), isFalse);
  });

  test('expectedCtc: null and locations: [] are sent explicitly (clears)', () {
    const dto = PreferencesUpdateDto(
      desiredRole: DesiredRole.design,
      locations: [],
      expectedCtc: null,
    );
    final json = dto.toJson();

    expect(json.containsKey('expected_ctc'), isTrue);
    expect(json['expected_ctc'], isNull);
    expect(json.containsKey('locations'), isTrue);
    expect(json['locations'], isEmpty);
  });
}
