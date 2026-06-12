import 'package:dio/dio.dart';

import 'package:jobify_app/data/employers/team/employer_invite_dto.dart';
import 'package:jobify_app/data/employers/team/member_dto.dart';

/// HTTP surface for R4 employer team management (members + invites).
class EmployerTeamApi {
  EmployerTeamApi(this._dio);
  final Dio _dio;

  // --- Members ---

  Future<List<MemberDto>> listMembers(String employerId) async {
    final res =
        await _dio.get<List<dynamic>>('/v1/employers/$employerId/members');
    return (res.data ?? [])
        .map((e) => MemberDto.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<MemberDto> addMember(
    String employerId, {
    required String email,
    required String role,
  }) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/v1/employers/$employerId/members',
      data: {'email': email, 'role': role},
    );
    return MemberDto.fromJson(res.data!);
  }

  Future<MemberDto> changeMemberRole(
    String employerId,
    String userId, {
    required String role,
  }) async {
    final res = await _dio.patch<Map<String, dynamic>>(
      '/v1/employers/$employerId/members/$userId',
      data: {'role': role},
    );
    return MemberDto.fromJson(res.data!);
  }

  Future<void> removeMember(String employerId, String userId) async {
    await _dio.delete<void>('/v1/employers/$employerId/members/$userId');
  }

  // --- Employer-managed invites ---

  Future<List<InviteDto>> listInvites(String employerId) async {
    final res =
        await _dio.get<List<dynamic>>('/v1/employers/$employerId/invites');
    return (res.data ?? [])
        .map((e) => InviteDto.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<InviteDto> createInvite(
    String employerId, {
    required String email,
    required String role,
  }) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/v1/employers/$employerId/invites',
      data: {'email': email, 'role': role},
    );
    return InviteDto.fromJson(res.data!);
  }

  Future<void> revokeInvite(String employerId, String inviteId) async {
    await _dio.delete<void>('/v1/employers/$employerId/invites/$inviteId');
  }

  // --- Invitee-facing ---

  Future<List<MyInviteDto>> listMyInvites() async {
    final res = await _dio.get<List<dynamic>>('/v1/me/invites');
    return (res.data ?? [])
        .map((e) => MyInviteDto.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<AcceptResultDto> acceptInvite(String inviteId) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/v1/me/invites/$inviteId/accept',
    );
    return AcceptResultDto.fromJson(res.data!);
  }

  Future<AcceptResultDto> declineInvite(String inviteId) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/v1/me/invites/$inviteId/decline',
    );
    return AcceptResultDto.fromJson(res.data!);
  }
}
