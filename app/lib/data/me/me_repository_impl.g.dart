// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'me_repository_impl.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(meRepository)
final meRepositoryProvider = MeRepositoryProvider._();

final class MeRepositoryProvider
    extends $FunctionalProvider<MeRepository, MeRepository, MeRepository>
    with $Provider<MeRepository> {
  MeRepositoryProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'meRepositoryProvider',
          isAutoDispose: false,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$meRepositoryHash();

  @$internal
  @override
  $ProviderElement<MeRepository> $createElement($ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  MeRepository create(Ref ref) {
    return meRepository(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(MeRepository value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<MeRepository>(value),
    );
  }
}

String _$meRepositoryHash() => r'cea52221e40ef2d011b52e8d6bb0187dbff1aa86';
