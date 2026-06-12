import 'package:jobify_app/data/employers/team/employer_invite_dto.dart';
import 'package:jobify_app/data/employers/team/member_dto.dart';

abstract interface class EmployerTeamRepository {
  Future<List<MemberDto>> listMembers(String employerId);
  Future<MemberDto> addMember(
    String employerId, {
    required String email,
    required String role,
  });
  Future<MemberDto> changeMemberRole(
    String employerId,
    String userId, {
    required String role,
  });
  Future<void> removeMember(String employerId, String userId);

  Future<List<InviteDto>> listInvites(String employerId);
  Future<InviteDto> createInvite(
    String employerId, {
    required String email,
    required String role,
  });
  Future<void> revokeInvite(String employerId, String inviteId);

  Future<List<MyInviteDto>> listMyInvites();
  Future<AcceptResultDto> acceptInvite(String inviteId);
  Future<AcceptResultDto> declineInvite(String inviteId);
}
