// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'preferences_repository_impl.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(preferencesRepository)
final preferencesRepositoryProvider = PreferencesRepositoryProvider._();

final class PreferencesRepositoryProvider extends $FunctionalProvider<
    PreferencesRepository,
    PreferencesRepository,
    PreferencesRepository> with $Provider<PreferencesRepository> {
  PreferencesRepositoryProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'preferencesRepositoryProvider',
          isAutoDispose: false,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$preferencesRepositoryHash();

  @$internal
  @override
  $ProviderElement<PreferencesRepository> $createElement(
          $ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  PreferencesRepository create(Ref ref) {
    return preferencesRepository(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(PreferencesRepository value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<PreferencesRepository>(value),
    );
  }
}

String _$preferencesRepositoryHash() =>
    r'7afb0165fe3bf2ee4fdad887620602acf3a25537';
