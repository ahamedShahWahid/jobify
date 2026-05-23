// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'applications_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(ApplicationsController)
final applicationsControllerProvider = ApplicationsControllerProvider._();

final class ApplicationsControllerProvider
    extends $AsyncNotifierProvider<ApplicationsController, ApplicationsState> {
  ApplicationsControllerProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'applicationsControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$applicationsControllerHash();

  @$internal
  @override
  ApplicationsController create() => ApplicationsController();
}

String _$applicationsControllerHash() =>
    r'572558e81048b7722754c4730269a53af8ee7bd9';

abstract class _$ApplicationsController
    extends $AsyncNotifier<ApplicationsState> {
  FutureOr<ApplicationsState> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref =
        this.ref as $Ref<AsyncValue<ApplicationsState>, ApplicationsState>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<AsyncValue<ApplicationsState>, ApplicationsState>,
        AsyncValue<ApplicationsState>,
        Object?,
        Object?>;
    element.handleCreate(ref, build);
  }
}
