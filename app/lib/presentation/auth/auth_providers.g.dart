// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'auth_providers.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Current auth state — SignedOut on app start; mutated by the bootstrap
/// controller (Task 24), the sign-in controller (Task 25), the sign-out
/// controller (Task 30), and the refresh interceptor's onSignedOut callback.

@ProviderFor(AuthStateNotifier)
final authStateProvider = AuthStateNotifierProvider._();

/// Current auth state — SignedOut on app start; mutated by the bootstrap
/// controller (Task 24), the sign-in controller (Task 25), the sign-out
/// controller (Task 30), and the refresh interceptor's onSignedOut callback.
final class AuthStateNotifierProvider
    extends $NotifierProvider<AuthStateNotifier, AuthState> {
  /// Current auth state — SignedOut on app start; mutated by the bootstrap
  /// controller (Task 24), the sign-in controller (Task 25), the sign-out
  /// controller (Task 30), and the refresh interceptor's onSignedOut callback.
  AuthStateNotifierProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'authStateProvider',
          isAutoDispose: false,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$authStateNotifierHash();

  @$internal
  @override
  AuthStateNotifier create() => AuthStateNotifier();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(AuthState value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<AuthState>(value),
    );
  }
}

String _$authStateNotifierHash() => r'6022514c6710b06bdbee8ada06541c090f3b9ec8';

/// Current auth state — SignedOut on app start; mutated by the bootstrap
/// controller (Task 24), the sign-in controller (Task 25), the sign-out
/// controller (Task 30), and the refresh interceptor's onSignedOut callback.

abstract class _$AuthStateNotifier extends $Notifier<AuthState> {
  AuthState build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<AuthState, AuthState>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<AuthState, AuthState>, AuthState, Object?, Object?>;
    element.handleCreate(ref, build);
  }
}
