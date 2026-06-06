// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'recruiter_jobs_repository_impl.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(recruiterJobsRepository)
final recruiterJobsRepositoryProvider = RecruiterJobsRepositoryProvider._();

final class RecruiterJobsRepositoryProvider extends $FunctionalProvider<
    RecruiterJobsRepository,
    RecruiterJobsRepository,
    RecruiterJobsRepository> with $Provider<RecruiterJobsRepository> {
  RecruiterJobsRepositoryProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'recruiterJobsRepositoryProvider',
          isAutoDispose: false,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$recruiterJobsRepositoryHash();

  @$internal
  @override
  $ProviderElement<RecruiterJobsRepository> $createElement(
          $ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  RecruiterJobsRepository create(Ref ref) {
    return recruiterJobsRepository(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(RecruiterJobsRepository value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<RecruiterJobsRepository>(value),
    );
  }
}

String _$recruiterJobsRepositoryHash() =>
    r'ff0acf2ddf99ae47bf9577095064a05850bc8336';
