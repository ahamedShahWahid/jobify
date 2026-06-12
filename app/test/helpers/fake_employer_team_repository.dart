import 'package:jobify_app/data/employers/team/employer_invite_dto.dart';
import 'package:jobify_app/data/employers/team/employer_team_repository.dart';
import 'package:jobify_app/data/employers/team/member_dto.dart';

/// Configurable in-memory [EmployerTeamRepository] for widget tests. Records
/// the last mutating call so assertions can verify the screen forwarded it.
class FakeEmployerTeamRepository implements EmployerTeamRepository {
  FakeEmployerTeamRepository({
    this.members = const [],
    this.invites = const [],
    this.myInvites = const [],
  });

  List<MemberDto> members;
  List<InviteDto> invites;
  List<MyInviteDto> myInvites;

  ({String employerId, String email, String role})? createdInvite;
  ({String employerId, String userId, String role})? changedRole;
  ({String employerId, String userId})? removed;
  ({String employerId, String inviteId})? revoked;
  String? acceptedId;
  String? declinedId;

  @override
  Future<List<MemberDto>> listMembers(String employerId) async => members;

  @override
  Future<MemberDto> addMember(
    String employerId, {
    required String email,
    required String role,
  }) async =>
      fakeMember(userId: 'new', email: email, role: role);

  @override
  Future<MemberDto> changeMemberRole(
    String employerId,
    String userId, {
    required String role,
  }) async {
    changedRole = (employerId: employerId, userId: userId, role: role);
    return fakeMember(userId: userId, role: role);
  }

  @override
  Future<void> removeMember(String employerId, String userId) async {
    removed = (employerId: employerId, userId: userId);
  }

  @override
  Future<List<InviteDto>> listInvites(String employerId) async => invites;

  @override
  Future<InviteDto> createInvite(
    String employerId, {
    required String email,
    required String role,
  }) async {
    createdInvite = (employerId: employerId, email: email, role: role);
    return fakeInvite(email: email, role: role);
  }

  @override
  Future<void> revokeInvite(String employerId, String inviteId) async {
    revoked = (employerId: employerId, inviteId: inviteId);
  }

  @override
  Future<List<MyInviteDto>> listMyInvites() async => myInvites;

  @override
  Future<AcceptResultDto> acceptInvite(String inviteId) async {
    acceptedId = inviteId;
    return const AcceptResultDto(
      employerId: 'e1',
      role: 'member',
      status: 'accepted',
    );
  }

  @override
  Future<AcceptResultDto> declineInvite(String inviteId) async {
    declinedId = inviteId;
    return const AcceptResultDto(
      employerId: 'e1',
      role: 'member',
      status: 'revoked',
    );
  }
}

MemberDto fakeMember({
  required String userId,
  String role = 'member',
  String? email = 'member@example.com',
  String? displayName = 'Member Person',
}) =>
    MemberDto(
      userId: userId,
      role: role,
      email: email,
      displayName: displayName,
      addedAt: DateTime.utc(2026),
    );

InviteDto fakeInvite({
  String id = 'inv1',
  String employerId = 'e1',
  String email = 'invitee@example.com',
  String role = 'member',
}) =>
    InviteDto(
      id: id,
      employerId: employerId,
      email: email,
      role: role,
      status: 'pending',
      expiresAt: DateTime.utc(2026, 12),
      createdAt: DateTime.utc(2026),
    );

MyInviteDto fakeMyInvite({
  String id = 'inv1',
  String employerId = 'e1',
  String employerName = 'Acme Corp',
  String role = 'member',
}) =>
    MyInviteDto(
      id: id,
      employerId: employerId,
      employerName: employerName,
      role: role,
      expiresAt: DateTime.utc(2026, 12),
      createdAt: DateTime.utc(2026),
    );
