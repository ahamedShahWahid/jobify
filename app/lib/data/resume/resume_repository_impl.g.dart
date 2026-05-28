// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'resume_repository_impl.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(resumeRepository)
final resumeRepositoryProvider = ResumeRepositoryProvider._();

final class ResumeRepositoryProvider extends $FunctionalProvider<
    ResumeRepository,
    ResumeRepository,
    ResumeRepository> with $Provider<ResumeRepository> {
  ResumeRepositoryProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'resumeRepositoryProvider',
          isAutoDispose: false,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$resumeRepositoryHash();

  @$internal
  @override
  $ProviderElement<ResumeRepository> $createElement($ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  ResumeRepository create(Ref ref) {
    return resumeRepository(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(ResumeRepository value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<ResumeRepository>(value),
    );
  }
}

String _$resumeRepositoryHash() => r'6767f09f77d8f65cd514a71a8f0b5a27519f7e9b';
