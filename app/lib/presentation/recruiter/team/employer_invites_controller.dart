import 'package:kpa_app/data/employers/team/employer_invite_dto.dart';
import 'package:kpa_app/data/employers/team/employer_team_repository_impl.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'employer_invites_controller.g.dart';

/// Pending invites for one employer. Family keyed by employerId.
@riverpod
Future<List<InviteDto>> employerInvitesController(Ref ref, String employerId) =>
    ref.read(employerTeamRepositoryProvider).listInvites(employerId);
