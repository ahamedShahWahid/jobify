import 'package:dio/dio.dart';
import 'package:jobify_app/data/api/dio_provider.dart';
import 'package:jobify_app/data/api/error_mapping.dart';
import 'package:jobify_app/data/employers/team/employer_invite_dto.dart';
import 'package:jobify_app/data/employers/team/employer_team_api.dart';
import 'package:jobify_app/data/employers/team/employer_team_repository.dart';
import 'package:jobify_app/data/employers/team/member_dto.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'employer_team_repository_impl.g.dart';

class EmployerTeamRepositoryImpl implements EmployerTeamRepository {
  EmployerTeamRepositoryImpl(this._api);
  final EmployerTeamApi _api;

  @override
  Future<List<MemberDto>> listMembers(String employerId) async {
    try {
      return await _api.listMembers(employerId);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<MemberDto> addMember(
    String employerId, {
    required String email,
    required String role,
  }) async {
    try {
      return await _api.addMember(employerId, email: email, role: role);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<MemberDto> changeMemberRole(
    String employerId,
    String userId, {
    required String role,
  }) async {
    try {
      return await _api.changeMemberRole(employerId, userId, role: role);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<void> removeMember(String employerId, String userId) async {
    try {
      await _api.removeMember(employerId, userId);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<List<InviteDto>> listInvites(String employerId) async {
    try {
      return await _api.listInvites(employerId);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<InviteDto> createInvite(
    String employerId, {
    required String email,
    required String role,
  }) async {
    try {
      return await _api.createInvite(employerId, email: email, role: role);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<void> revokeInvite(String employerId, String inviteId) async {
    try {
      await _api.revokeInvite(employerId, inviteId);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<List<MyInviteDto>> listMyInvites() async {
    try {
      return await _api.listMyInvites();
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<AcceptResultDto> acceptInvite(String inviteId) async {
    try {
      return await _api.acceptInvite(inviteId);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }

  @override
  Future<AcceptResultDto> declineInvite(String inviteId) async {
    try {
      return await _api.declineInvite(inviteId);
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }
}

@Riverpod(keepAlive: true)
EmployerTeamRepository employerTeamRepository(Ref ref) =>
    EmployerTeamRepositoryImpl(EmployerTeamApi(ref.read(dioProvider)));
