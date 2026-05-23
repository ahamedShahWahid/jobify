// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'saved_jobs_repository_impl.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(savedJobsRepository)
final savedJobsRepositoryProvider = SavedJobsRepositoryProvider._();

final class SavedJobsRepositoryProvider extends $FunctionalProvider<
    SavedJobsRepository,
    SavedJobsRepository,
    SavedJobsRepository> with $Provider<SavedJobsRepository> {
  SavedJobsRepositoryProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'savedJobsRepositoryProvider',
          isAutoDispose: false,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$savedJobsRepositoryHash();

  @$internal
  @override
  $ProviderElement<SavedJobsRepository> $createElement(
          $ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  SavedJobsRepository create(Ref ref) {
    return savedJobsRepository(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(SavedJobsRepository value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<SavedJobsRepository>(value),
    );
  }
}

String _$savedJobsRepositoryHash() =>
    r'71e889e049eb12b3c1ffe99a38292fcb6998ee18';
