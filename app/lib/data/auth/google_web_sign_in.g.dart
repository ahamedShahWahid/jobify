// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'google_web_sign_in.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Initialized [GoogleWebSignIn]. Awaiting [initialize] inside the provider
/// guarantees the widget tree only reaches [GoogleWebSignIn.button] after the
/// GIS client is ready.

@ProviderFor(googleWebSignIn)
final googleWebSignInProvider = GoogleWebSignInProvider._();

/// Initialized [GoogleWebSignIn]. Awaiting [initialize] inside the provider
/// guarantees the widget tree only reaches [GoogleWebSignIn.button] after the
/// GIS client is ready.

final class GoogleWebSignInProvider extends $FunctionalProvider<
        AsyncValue<GoogleWebSignIn>, GoogleWebSignIn, FutureOr<GoogleWebSignIn>>
    with $FutureModifier<GoogleWebSignIn>, $FutureProvider<GoogleWebSignIn> {
  /// Initialized [GoogleWebSignIn]. Awaiting [initialize] inside the provider
  /// guarantees the widget tree only reaches [GoogleWebSignIn.button] after the
  /// GIS client is ready.
  GoogleWebSignInProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'googleWebSignInProvider',
          isAutoDispose: false,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$googleWebSignInHash();

  @$internal
  @override
  $FutureProviderElement<GoogleWebSignIn> $createElement(
          $ProviderPointer pointer) =>
      $FutureProviderElement(pointer);

  @override
  FutureOr<GoogleWebSignIn> create(Ref ref) {
    return googleWebSignIn(ref);
  }
}

String _$googleWebSignInHash() => r'8d6288b2e02bf500e29126aab80bba386fbb0cf8';
