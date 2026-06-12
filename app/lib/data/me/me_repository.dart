import 'package:jobify_app/data/me/me_dto.dart';
import 'package:jobify_app/data/me/profile_update_dto.dart';

abstract interface class MeRepository {
  Future<MeDto> fetch();
  Future<MeDto> updateProfile(ProfileUpdateDto update);
}
