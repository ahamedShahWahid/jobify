// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'notifications_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(NotificationsController)
final notificationsControllerProvider = NotificationsControllerProvider._();

final class NotificationsControllerProvider extends $AsyncNotifierProvider<
    NotificationsController, NotificationsState> {
  NotificationsControllerProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'notificationsControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$notificationsControllerHash();

  @$internal
  @override
  NotificationsController create() => NotificationsController();
}

String _$notificationsControllerHash() =>
    r'f09c0598522996bcf628e2453d67dcae44c771ae';

abstract class _$NotificationsController
    extends $AsyncNotifier<NotificationsState> {
  FutureOr<NotificationsState> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref =
        this.ref as $Ref<AsyncValue<NotificationsState>, NotificationsState>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<AsyncValue<NotificationsState>, NotificationsState>,
        AsyncValue<NotificationsState>,
        Object?,
        Object?>;
    element.handleCreate(ref, build);
  }
}
