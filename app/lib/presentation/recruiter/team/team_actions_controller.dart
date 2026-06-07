import 'package:kpa_app/data/employers/team/employer_team_repository_impl.dart';
import 'package:kpa_app/presentation/recruiter/team/employer_invites_controller.dart';
import 'package:kpa_app/presentation/recruiter/team/members_controller.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'team_actions_controller.g.dart';

/// Owner-only mutations on an employer's team. Each method runs through
/// `AsyncValue.guard` and invalidates the affected employer's roster + invites
/// controllers so the lists refetch (no in-place list mutation — mirrors the
/// applicant-side convention).
@riverpod
class TeamActionsController extends _$TeamActionsController {
  @override
  FutureOr<void> build() {}

  void _invalidate(String employerId) {
    ref
      ..invalidate(membersControllerProvider(employerId))
      ..invalidate(employerInvitesControllerProvider(employerId));
  }

  Future<bool> addMember(
    String employerId, {
    required String email,
    required String role,
  }) =>
      _run(() async {
        await ref
            .read(employerTeamRepositoryProvider)
            .addMember(employerId, email: email, role: role);
        _invalidate(employerId);
      });

  Future<bool> changeRole(
    String employerId,
    String userId, {
    required String role,
  }) =>
      _run(() async {
        await ref
            .read(employerTeamRepositoryProvider)
            .changeMemberRole(employerId, userId, role: role);
        _invalidate(employerId);
      });

  Future<bool> removeMember(String employerId, String userId) => _run(() async {
        await ref
            .read(employerTeamRepositoryProvider)
            .removeMember(employerId, userId);
        _invalidate(employerId);
      });

  Future<bool> createInvite(
    String employerId, {
    required String email,
    required String role,
  }) =>
      _run(() async {
        await ref
            .read(employerTeamRepositoryProvider)
            .createInvite(employerId, email: email, role: role);
        _invalidate(employerId);
      });

  Future<bool> revokeInvite(String employerId, String inviteId) =>
      _run(() async {
        await ref
            .read(employerTeamRepositoryProvider)
            .revokeInvite(employerId, inviteId);
        _invalidate(employerId);
      });

  /// Runs [action], surfacing success/failure as a bool while still recording
  /// the error on `state` (so screens can read `state.error` for a message).
  Future<bool> _run(Future<void> Function() action) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(action);
    return !state.hasError;
  }
}
