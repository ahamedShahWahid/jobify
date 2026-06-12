import 'package:jobify_app/data/auth/user_role.dart';
import 'package:jobify_app/presentation/routing/routes.dart';

/// True if [loc] belongs to the recruiter shell subtree.
bool isRecruiterLocation(String loc) => loc.startsWith('/recruiter');

/// True if [loc] is an applicant-shell location (the four applicant tabs
/// and their nested routes). Onboarding is treated as applicant-only.
bool isApplicantShellLocation(String loc) =>
    loc.startsWith(Routes.feed) ||
    loc.startsWith(Routes.saved) ||
    loc.startsWith(Routes.applications) ||
    loc.startsWith(Routes.profile);

/// Returns the path to redirect a SIGNED-IN user to based on their [role] and
/// current [loc], or null to stay put. Caller handles the signed-out case.
String? roleAwareRedirect({required UserRole role, required String loc}) {
  if (role.usesRecruiterShell) {
    // A recruiter on an applicant-only location (incl. onboarding) → dashboard.
    if (isApplicantShellLocation(loc) || loc == Routes.onboardingEmployer) {
      return Routes.recruiterDashboard;
    }
    return null;
  }
  // Applicant on a recruiter location → feed.
  if (isRecruiterLocation(loc)) return Routes.feed;
  return null;
}
