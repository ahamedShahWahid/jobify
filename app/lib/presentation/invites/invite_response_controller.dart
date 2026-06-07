import 'package:kpa_app/data/auth/auth_repository_provider.dart';
import 'package:kpa_app/data/employers/team/employer_team_repository_impl.dart';
import 'package:kpa_app/presentation/invites/my_invites_controller.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'invite_response_controller.g.dart';

/// Accept / decline a pending invitation.
///
/// On **accept** we refresh the session (`/v1/me`) so the new RECRUITER role
/// propagates into `authStateProvider`; the role-aware redirect then moves the
/// user into the recruiter shell — same "act then refreshSession" pattern as
/// employer onboarding. Decline just refetches the invite list.
@riverpod
class InviteResponseController extends _$InviteResponseController {
  @override
  FutureOr<void> build() {}

  Future<bool> accept(String inviteId) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      await ref.read(employerTeamRepositoryProvider).acceptInvite(inviteId);
      ref.invalidate(myInvitesControllerProvider);
      await ref.read(authRepositoryProvider).refreshSession();
    });
    return !state.hasError;
  }

  Future<bool> decline(String inviteId) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      await ref.read(employerTeamRepositoryProvider).declineInvite(inviteId);
      ref.invalidate(myInvitesControllerProvider);
    });
    return !state.hasError;
  }
}
