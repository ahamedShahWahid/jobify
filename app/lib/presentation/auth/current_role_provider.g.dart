// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'current_role_provider.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// The signed-in user's role, or null when not signed in.

@ProviderFor(currentRole)
final currentRoleProvider = CurrentRoleProvider._();

/// The signed-in user's role, or null when not signed in.

final class CurrentRoleProvider
    extends $FunctionalProvider<UserRole?, UserRole?, UserRole?>
    with $Provider<UserRole?> {
  /// The signed-in user's role, or null when not signed in.
  CurrentRoleProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'currentRoleProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$currentRoleHash();

  @$internal
  @override
  $ProviderElement<UserRole?> $createElement($ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  UserRole? create(Ref ref) {
    return currentRole(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(UserRole? value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<UserRole?>(value),
    );
  }
}

String _$currentRoleHash() => r'b857bcb435bad208476372d8b06cb0fb69da8e6f';
