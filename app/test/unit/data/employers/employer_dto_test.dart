import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/employers/employer_dto.dart';

void main() {
  test('parses a verified employer', () {
    final dto = EmployerDto.fromJson({
      'id': 'emp1',
      'name': 'Acme',
      'gst': '22AAAAA0000A1Z5',
      'verified_at': '2026-01-01T00:00:00Z',
      'created_at': '2026-01-01T00:00:00Z',
    });
    expect(dto.name, 'Acme');
    expect(dto.gst, '22AAAAA0000A1Z5');
    expect(dto.isVerified, isTrue);
  });

  test('parses an unverified employer with null gst', () {
    final dto = EmployerDto.fromJson({
      'id': 'emp2',
      'name': 'Beta',
      'gst': null,
      'verified_at': null,
      'created_at': '2026-01-01T00:00:00Z',
    });
    expect(dto.gst, isNull);
    expect(dto.isVerified, isFalse);
  });
}
