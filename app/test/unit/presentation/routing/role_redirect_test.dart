import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/auth/user_role.dart';
import 'package:kpa_app/presentation/routing/role_redirect.dart';
import 'package:kpa_app/presentation/routing/routes.dart';

void main() {
  test('recruiter on applicant route is bounced to dashboard', () {
    expect(roleAwareRedirect(role: UserRole.recruiter, loc: Routes.feed),
        Routes.recruiterDashboard);
    expect(roleAwareRedirect(role: UserRole.recruiter, loc: '/profile/resume'),
        Routes.recruiterDashboard);
    expect(
        roleAwareRedirect(
            role: UserRole.recruiter, loc: Routes.onboardingEmployer),
        Routes.recruiterDashboard);
  });

  test('recruiter on a recruiter route stays', () {
    expect(
        roleAwareRedirect(role: UserRole.recruiter, loc: Routes.recruiterJobs),
        isNull);
  });

  test('applicant on a recruiter route is bounced to feed', () {
    expect(
        roleAwareRedirect(
            role: UserRole.applicant, loc: Routes.recruiterDashboard),
        Routes.feed);
  });

  test('applicant on an applicant route stays', () {
    expect(
        roleAwareRedirect(role: UserRole.applicant, loc: Routes.feed), isNull);
    expect(
        roleAwareRedirect(
            role: UserRole.applicant, loc: Routes.onboardingEmployer),
        isNull);
  });

  test('admin uses the recruiter shell', () {
    expect(roleAwareRedirect(role: UserRole.admin, loc: Routes.feed),
        Routes.recruiterDashboard);
  });
}
