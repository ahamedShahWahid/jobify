import 'package:kpa_app/data/me/me_dto.dart';
import 'package:kpa_app/data/me/me_repository_impl.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'me_controller.g.dart';

@riverpod
class MeController extends _$MeController {
  @override
  Future<MeDto> build() async => ref.read(meRepositoryProvider).fetch();

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }
}
