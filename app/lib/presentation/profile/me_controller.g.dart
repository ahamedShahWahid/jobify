// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'me_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(MeController)
final meControllerProvider = MeControllerProvider._();

final class MeControllerProvider
    extends $AsyncNotifierProvider<MeController, MeDto> {
  MeControllerProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'meControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$meControllerHash();

  @$internal
  @override
  MeController create() => MeController();
}

String _$meControllerHash() => r'60cfe3297baa40628e8c30bb78d525cadfada359';

abstract class _$MeController extends $AsyncNotifier<MeDto> {
  FutureOr<MeDto> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<AsyncValue<MeDto>, MeDto>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<AsyncValue<MeDto>, MeDto>,
        AsyncValue<MeDto>,
        Object?,
        Object?>;
    element.handleCreate(ref, build);
  }
}
