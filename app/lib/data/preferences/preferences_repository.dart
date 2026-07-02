import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';

abstract interface class PreferencesRepository {
  Future<PreferencesDto> fetch();
  Future<PreferencesDto> update(PreferencesUpdateDto update);
}
