import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/core/error/exceptions.dart';
import 'package:jobify_app/data/me/me_dto.dart';
import 'package:jobify_app/data/me/me_repository.dart';
import 'package:jobify_app/data/me/me_repository_impl.dart';
import 'package:jobify_app/data/me/profile_update_dto.dart';
import 'package:jobify_app/presentation/profile/profile_edit_controller.dart';

class _OkRepo implements MeRepository {
  @override
  Future<MeDto> fetch() async =>
      const MeDto(id: 'u1', email: 'e', role: 'applicant');
  @override
  Future<MeDto> updateProfile(ProfileUpdateDto u) async =>
      const MeDto(id: 'u1', email: 'e', role: 'applicant');
}

class _ErrRepo implements MeRepository {
  @override
  Future<MeDto> fetch() async =>
      const MeDto(id: 'u1', email: 'e', role: 'applicant');
  @override
  Future<MeDto> updateProfile(ProfileUpdateDto u) async =>
      throw const ApiException(statusCode: 422, slug: 'bad');
}

const _update = ProfileUpdateDto(fullName: 'A', locations: ['Pune']);

void main() {
  test('submit success returns true', () async {
    final c = ProviderContainer(
      overrides: [meRepositoryProvider.overrideWithValue(_OkRepo())],
    );
    addTearDown(c.dispose);
    final ok =
        await c.read(profileEditControllerProvider.notifier).submit(_update);
    expect(ok, isTrue);
  });

  test('submit error returns false and sets error state', () async {
    final c = ProviderContainer(
      overrides: [meRepositoryProvider.overrideWithValue(_ErrRepo())],
    );
    addTearDown(c.dispose);
    final ok =
        await c.read(profileEditControllerProvider.notifier).submit(_update);
    expect(ok, isFalse);
    expect(c.read(profileEditControllerProvider).hasError, isTrue);
  });
}
