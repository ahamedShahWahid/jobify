import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/me/me_dto.dart';

// Fixture mirrors the REAL GET /v1/me wire shape (api/src/jobify/routes/me.py),
// verified against tests/integration/test_me.py. User fields are flat; the
// applicant is nested; and Pydantic serializes Decimal CTC/experience to
// JSON *strings*. Guards the contract so a backend/DTO drift fails here, not
// as a blank "Something went wrong" screen on a 200.
void main() {
  test('MeDto.fromJson parses the flat /v1/me shape with nested applicant', () {
    final dto = MeDto.fromJson(const {
      'id': 'u1',
      'email': 'alice@example.com',
      'role': 'applicant',
      'applicant': {
        'id': 'a1',
        'full_name': 'Alice',
        'locations': ['Pune'],
        'notice_period_days': 30,
        'current_ctc': '1200000.50',
        'expected_ctc': '1500000',
        'years_experience': '4.5',
      },
    });

    expect(dto.id, 'u1');
    expect(dto.email, 'alice@example.com');
    expect(dto.role, 'applicant');
    // /v1/me does not emit display_name today — must be null, not a throw.
    expect(dto.displayName, isNull);

    final applicant = dto.applicant!;
    expect(applicant.id, 'a1');
    expect(applicant.fullName, 'Alice');
    expect(applicant.locations, ['Pune']);
    expect(applicant.noticePeriodDays, 30);
    // Decimal-on-the-wire is a string.
    expect(applicant.currentCtc, '1200000.50');
    expect(applicant.yearsExperience, '4.5');
  });

  test('MeDto.fromJson parses a null applicant (non-applicant roles)', () {
    final dto = MeDto.fromJson(const {
      'id': 'u2',
      'email': 'rec@example.com',
      'role': 'recruiter',
      'applicant': null,
    });

    expect(dto.applicant, isNull);
  });
}
