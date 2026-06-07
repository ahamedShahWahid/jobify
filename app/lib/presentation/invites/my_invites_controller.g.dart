// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'my_invites_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Pending employer invitations addressed to the signed-in user.

@ProviderFor(MyInvitesController)
final myInvitesControllerProvider = MyInvitesControllerProvider._();

/// Pending employer invitations addressed to the signed-in user.
final class MyInvitesControllerProvider
    extends $AsyncNotifierProvider<MyInvitesController, List<MyInviteDto>> {
  /// Pending employer invitations addressed to the signed-in user.
  MyInvitesControllerProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'myInvitesControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$myInvitesControllerHash();

  @$internal
  @override
  MyInvitesController create() => MyInvitesController();
}

String _$myInvitesControllerHash() =>
    r'7cb01cba57f3c032be9195bd9753dd88db84733e';

/// Pending employer invitations addressed to the signed-in user.

abstract class _$MyInvitesController extends $AsyncNotifier<List<MyInviteDto>> {
  FutureOr<List<MyInviteDto>> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref =
        this.ref as $Ref<AsyncValue<List<MyInviteDto>>, List<MyInviteDto>>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<AsyncValue<List<MyInviteDto>>, List<MyInviteDto>>,
        AsyncValue<List<MyInviteDto>>,
        Object?,
        Object?>;
    element.handleCreate(ref, build);
  }
}
