// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'active_employer_provider.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(recruiterEmployers)
final recruiterEmployersProvider = RecruiterEmployersProvider._();

final class RecruiterEmployersProvider extends $FunctionalProvider<
        AsyncValue<List<EmployerDto>>,
        List<EmployerDto>,
        FutureOr<List<EmployerDto>>>
    with
        $FutureModifier<List<EmployerDto>>,
        $FutureProvider<List<EmployerDto>> {
  RecruiterEmployersProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'recruiterEmployersProvider',
          isAutoDispose: false,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$recruiterEmployersHash();

  @$internal
  @override
  $FutureProviderElement<List<EmployerDto>> $createElement(
          $ProviderPointer pointer) =>
      $FutureProviderElement(pointer);

  @override
  FutureOr<List<EmployerDto>> create(Ref ref) {
    return recruiterEmployers(ref);
  }
}

String _$recruiterEmployersHash() =>
    r'84b64811b4e0ccce81c271f1578d4260c0977090';

@ProviderFor(ActiveEmployer)
final activeEmployerProvider = ActiveEmployerProvider._();

final class ActiveEmployerProvider
    extends $NotifierProvider<ActiveEmployer, EmployerDto?> {
  ActiveEmployerProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'activeEmployerProvider',
          isAutoDispose: false,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$activeEmployerHash();

  @$internal
  @override
  ActiveEmployer create() => ActiveEmployer();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(EmployerDto? value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<EmployerDto?>(value),
    );
  }
}

String _$activeEmployerHash() => r'a0f018fe570ce9c2d92bf467f53fdbbf1e34ffe6';

abstract class _$ActiveEmployer extends $Notifier<EmployerDto?> {
  EmployerDto? build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<EmployerDto?, EmployerDto?>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<EmployerDto?, EmployerDto?>,
        EmployerDto?,
        Object?,
        Object?>;
    element.handleCreate(ref, build);
  }
}
