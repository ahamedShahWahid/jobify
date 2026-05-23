// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'bootstrap_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(BootstrapController)
final bootstrapControllerProvider = BootstrapControllerProvider._();

final class BootstrapControllerProvider
    extends $AsyncNotifierProvider<BootstrapController, BootstrapOutcome> {
  BootstrapControllerProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'bootstrapControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$bootstrapControllerHash();

  @$internal
  @override
  BootstrapController create() => BootstrapController();
}

String _$bootstrapControllerHash() =>
    r'5346c7df0c233997f407f52fad398c46306c2d6a';

abstract class _$BootstrapController extends $AsyncNotifier<BootstrapOutcome> {
  FutureOr<BootstrapOutcome> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref =
        this.ref as $Ref<AsyncValue<BootstrapOutcome>, BootstrapOutcome>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<AsyncValue<BootstrapOutcome>, BootstrapOutcome>,
        AsyncValue<BootstrapOutcome>,
        Object?,
        Object?>;
    element.handleCreate(ref, build);
  }
}
