// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'employer_onboarding_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(EmployerOnboardingController)
final employerOnboardingControllerProvider =
    EmployerOnboardingControllerProvider._();

final class EmployerOnboardingControllerProvider
    extends $AsyncNotifierProvider<EmployerOnboardingController, EmployerDto?> {
  EmployerOnboardingControllerProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'employerOnboardingControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$employerOnboardingControllerHash();

  @$internal
  @override
  EmployerOnboardingController create() => EmployerOnboardingController();
}

String _$employerOnboardingControllerHash() =>
    r'0a9c62a38695d3fc3a9863f5fce03d58f3bc41a9';

abstract class _$EmployerOnboardingController
    extends $AsyncNotifier<EmployerDto?> {
  FutureOr<EmployerDto?> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<AsyncValue<EmployerDto?>, EmployerDto?>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<AsyncValue<EmployerDto?>, EmployerDto?>,
        AsyncValue<EmployerDto?>,
        Object?,
        Object?>;
    element.handleCreate(ref, build);
  }
}
