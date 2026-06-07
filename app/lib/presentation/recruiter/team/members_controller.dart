import 'package:kpa_app/data/employers/team/employer_team_repository_impl.dart';
import 'package:kpa_app/data/employers/team/member_dto.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'members_controller.g.dart';

/// The roster for one employer. Family keyed by employerId.
@riverpod
Future<List<MemberDto>> membersController(Ref ref, String employerId) =>
    ref.read(employerTeamRepositoryProvider).listMembers(employerId);
