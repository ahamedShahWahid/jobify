/// Centralised route path constants. Keep in sync with the redirect
/// guards in router.dart.
abstract final class Routes {
  static const splash = '/';
  static const signIn = '/signin';
  static const feed = '/feed';
  static const saved = '/saved';
  static const applications = '/applications';
  static const profile = '/profile';
  static const profileEdit = '/profile/edit';
  static const resume = '/profile/resume';
  static const notifications = '/profile/notifications';
  static const privacy = '/profile/privacy';
  static const privacyDelete = '/profile/privacy/delete';

  // Onboarding (applicant → recruiter).
  static const onboardingEmployer = '/onboarding/employer';

  // Recruiter shell.
  static const recruiterDashboard = '/recruiter/dashboard';
  static const recruiterJobs = '/recruiter/jobs';
  static const recruiterJobNew = '/recruiter/jobs/new';
  static const recruiterEmployer = '/recruiter/employer';
  static const recruiterProfile = '/recruiter/profile';
}
