import 'package:kpa_app/data/employers/team/employer_invite_dto.dart';
import 'package:kpa_app/data/employers/team/employer_team_repository_impl.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'my_invites_controller.g.dart';

/// Pending employer invitations addressed to the signed-in user.
@riverpod
class MyInvitesController extends _$MyInvitesController {
  @override
  Future<List<MyInviteDto>> build() =>
      ref.read(employerTeamRepositoryProvider).listMyInvites();

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }
}
