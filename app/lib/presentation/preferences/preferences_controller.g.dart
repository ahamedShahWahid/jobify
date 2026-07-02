// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'preferences_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(PreferencesController)
final preferencesControllerProvider = PreferencesControllerProvider._();

final class PreferencesControllerProvider
    extends $AsyncNotifierProvider<PreferencesController, PreferencesDto> {
  PreferencesControllerProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'preferencesControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$preferencesControllerHash();

  @$internal
  @override
  PreferencesController create() => PreferencesController();
}

String _$preferencesControllerHash() =>
    r'd04453cfd6067f093043693662defbc24662a73a';

abstract class _$PreferencesController extends $AsyncNotifier<PreferencesDto> {
  FutureOr<PreferencesDto> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<AsyncValue<PreferencesDto>, PreferencesDto>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<AsyncValue<PreferencesDto>, PreferencesDto>,
        AsyncValue<PreferencesDto>,
        Object?,
        Object?>;
    element.handleCreate(ref, build);
  }
}
