// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'withdraw_application_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(WithdrawApplicationController)
final withdrawApplicationControllerProvider =
    WithdrawApplicationControllerFamily._();

final class WithdrawApplicationControllerProvider
    extends $AsyncNotifierProvider<WithdrawApplicationController,
        ApplicationDto?> {
  WithdrawApplicationControllerProvider._(
      {required WithdrawApplicationControllerFamily super.from,
      required String super.argument})
      : super(
          retry: null,
          name: r'withdrawApplicationControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$withdrawApplicationControllerHash();

  @override
  String toString() {
    return r'withdrawApplicationControllerProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  WithdrawApplicationController create() => WithdrawApplicationController();

  @override
  bool operator ==(Object other) {
    return other is WithdrawApplicationControllerProvider &&
        other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$withdrawApplicationControllerHash() =>
    r'dd888a58e5420f413e7af6816ae7a4486839e753';

final class WithdrawApplicationControllerFamily extends $Family
    with
        $ClassFamilyOverride<
            WithdrawApplicationController,
            AsyncValue<ApplicationDto?>,
            ApplicationDto?,
            FutureOr<ApplicationDto?>,
            String> {
  WithdrawApplicationControllerFamily._()
      : super(
          retry: null,
          name: r'withdrawApplicationControllerProvider',
          dependencies: null,
          $allTransitiveDependencies: null,
          isAutoDispose: true,
        );

  WithdrawApplicationControllerProvider call(
    String applicationId,
  ) =>
      WithdrawApplicationControllerProvider._(
          argument: applicationId, from: this);

  @override
  String toString() => r'withdrawApplicationControllerProvider';
}

abstract class _$WithdrawApplicationController
    extends $AsyncNotifier<ApplicationDto?> {
  late final _$args = ref.$arg as String;
  String get applicationId => _$args;

  FutureOr<ApplicationDto?> build(
    String applicationId,
  );
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<AsyncValue<ApplicationDto?>, ApplicationDto?>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<AsyncValue<ApplicationDto?>, ApplicationDto?>,
        AsyncValue<ApplicationDto?>,
        Object?,
        Object?>;
    element.handleCreate(
        ref,
        () => build(
              _$args,
            ));
  }
}
