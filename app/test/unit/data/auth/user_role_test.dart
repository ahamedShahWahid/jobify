import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/auth/user_role.dart';

void main() {
  test('fromWire maps known roles', () {
    expect(UserRole.fromWire('applicant'), UserRole.applicant);
    expect(UserRole.fromWire('recruiter'), UserRole.recruiter);
    expect(UserRole.fromWire('admin'), UserRole.admin);
  });

  test('fromWire maps unknown values to the sentinel', () {
    expect(UserRole.fromWire('superuser'), UserRole.unknown);
    expect(UserRole.fromWire(''), UserRole.unknown);
  });

  test('usesRecruiterShell true for recruiter and admin only', () {
    expect(UserRole.recruiter.usesRecruiterShell, isTrue);
    expect(UserRole.admin.usesRecruiterShell, isTrue);
    expect(UserRole.applicant.usesRecruiterShell, isFalse);
    expect(UserRole.unknown.usesRecruiterShell, isFalse);
  });
}
