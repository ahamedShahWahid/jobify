// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'sign_out_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(SignOutController)
final signOutControllerProvider = SignOutControllerProvider._();

final class SignOutControllerProvider
    extends $AsyncNotifierProvider<SignOutController, void> {
  SignOutControllerProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'signOutControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$signOutControllerHash();

  @$internal
  @override
  SignOutController create() => SignOutController();
}

String _$signOutControllerHash() => r'f35d6d1cf5df2ac84daa38c396d255b3a5b6cf05';

abstract class _$SignOutController extends $AsyncNotifier<void> {
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
