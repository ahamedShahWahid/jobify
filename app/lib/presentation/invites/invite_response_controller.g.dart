// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'invite_response_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Accept / decline a pending invitation.
///
/// On **accept** we refresh the session (`/v1/me`) so the new RECRUITER role
/// propagates into `authStateProvider`; the role-aware redirect then moves the
/// user into the recruiter shell — same "act then refreshSession" pattern as
/// employer onboarding. Decline just refetches the invite list.

@ProviderFor(InviteResponseController)
final inviteResponseControllerProvider = InviteResponseControllerProvider._();

/// Accept / decline a pending invitation.
///
/// On **accept** we refresh the session (`/v1/me`) so the new RECRUITER role
/// propagates into `authStateProvider`; the role-aware redirect then moves the
/// user into the recruiter shell — same "act then refreshSession" pattern as
/// employer onboarding. Decline just refetches the invite list.
final class InviteResponseControllerProvider
    extends $AsyncNotifierProvider<InviteResponseController, void> {
  /// Accept / decline a pending invitation.
  ///
  /// On **accept** we refresh the session (`/v1/me`) so the new RECRUITER role
  /// propagates into `authStateProvider`; the role-aware redirect then moves the
  /// user into the recruiter shell — same "act then refreshSession" pattern as
  /// employer onboarding. Decline just refetches the invite list.
  InviteResponseControllerProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'inviteResponseControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$inviteResponseControllerHash();

  @$internal
  @override
  InviteResponseController create() => InviteResponseController();
}

String _$inviteResponseControllerHash() =>
    r'b4bd67d26406551d893bdcfbc89cc98abd7d5c9f';

/// Accept / decline a pending invitation.
///
/// On **accept** we refresh the session (`/v1/me`) so the new RECRUITER role
/// propagates into `authStateProvider`; the role-aware redirect then moves the
/// user into the recruiter shell — same "act then refreshSession" pattern as
/// employer onboarding. Decline just refetches the invite list.

abstract class _$InviteResponseController extends $AsyncNotifier<void> {
  FutureOr<void> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<AsyncValue<void>, void>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<AsyncValue<void>, void>,
        AsyncValue<void>,
        Object?,
        Object?>;
    element.handleCreate(ref, build);
  }
}
