// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'employer_repository_impl.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(employerRepository)
final employerRepositoryProvider = EmployerRepositoryProvider._();

final class EmployerRepositoryProvider extends $FunctionalProvider<
    EmployerRepository,
    EmployerRepository,
    EmployerRepository> with $Provider<EmployerRepository> {
  EmployerRepositoryProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'employerRepositoryProvider',
          isAutoDispose: false,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$employerRepositoryHash();

  @$internal
  @override
  $ProviderElement<EmployerRepository> $createElement(
          $ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  EmployerRepository create(Ref ref) {
    return employerRepository(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(EmployerRepository value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<EmployerRepository>(value),
    );
  }
}

String _$employerRepositoryHash() =>
    r'2113ee944b0122cd95701cf65781cd2f59a3ed61';
