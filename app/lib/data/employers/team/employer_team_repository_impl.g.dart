// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'employer_team_repository_impl.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(employerTeamRepository)
final employerTeamRepositoryProvider = EmployerTeamRepositoryProvider._();

final class EmployerTeamRepositoryProvider extends $FunctionalProvider<
    EmployerTeamRepository,
    EmployerTeamRepository,
    EmployerTeamRepository> with $Provider<EmployerTeamRepository> {
  EmployerTeamRepositoryProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'employerTeamRepositoryProvider',
          isAutoDispose: false,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$employerTeamRepositoryHash();

  @$internal
  @override
  $ProviderElement<EmployerTeamRepository> $createElement(
          $ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  EmployerTeamRepository create(Ref ref) {
    return employerTeamRepository(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(EmployerTeamRepository value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<EmployerTeamRepository>(value),
    );
  }
}

String _$employerTeamRepositoryHash() =>
    r'6fe70c76efaa6a08d16a703751bc326883c300d3';
