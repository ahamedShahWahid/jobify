// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'dio_provider.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(accessTokenHolder)
final accessTokenHolderProvider = AccessTokenHolderProvider._();

final class AccessTokenHolderProvider extends $FunctionalProvider<
    AccessTokenHolder,
    AccessTokenHolder,
    AccessTokenHolder> with $Provider<AccessTokenHolder> {
  AccessTokenHolderProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'accessTokenHolderProvider',
          isAutoDispose: false,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$accessTokenHolderHash();

  @$internal
  @override
  $ProviderElement<AccessTokenHolder> $createElement(
          $ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  AccessTokenHolder create(Ref ref) {
    return accessTokenHolder(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(AccessTokenHolder value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<AccessTokenHolder>(value),
    );
  }
}

String _$accessTokenHolderHash() => r'7a899a8bacf1f8b46ebd99e98f992f85e89bdd27';

@ProviderFor(dio)
final dioProvider = DioProvider._();

final class DioProvider extends $FunctionalProvider<Dio, Dio, Dio>
    with $Provider<Dio> {
  DioProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'dioProvider',
          isAutoDispose: false,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$dioHash();

  @$internal
  @override
  $ProviderElement<Dio> $createElement($ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  Dio create(Ref ref) {
    return dio(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(Dio value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<Dio>(value),
    );
  }
}

String _$dioHash() => r'549cc3f9a8d1191260723f1c344fd491439852c6';
