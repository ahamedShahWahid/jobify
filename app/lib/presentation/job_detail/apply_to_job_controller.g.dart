// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'apply_to_job_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(ApplyToJobController)
final applyToJobControllerProvider = ApplyToJobControllerFamily._();

final class ApplyToJobControllerProvider
    extends $AsyncNotifierProvider<ApplyToJobController, ApplicationDto?> {
  ApplyToJobControllerProvider._(
      {required ApplyToJobControllerFamily super.from,
      required String super.argument})
      : super(
          retry: null,
          name: r'applyToJobControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$applyToJobControllerHash();

  @override
  String toString() {
    return r'applyToJobControllerProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  ApplyToJobController create() => ApplyToJobController();

  @override
  bool operator ==(Object other) {
    return other is ApplyToJobControllerProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$applyToJobControllerHash() =>
    r'421c40110a2cfef0fc5cb90fa218ef63c0f93477';

final class ApplyToJobControllerFamily extends $Family
    with
        $ClassFamilyOverride<ApplyToJobController, AsyncValue<ApplicationDto?>,
            ApplicationDto?, FutureOr<ApplicationDto?>, String> {
  ApplyToJobControllerFamily._()
      : super(
          retry: null,
          name: r'applyToJobControllerProvider',
          dependencies: null,
          $allTransitiveDependencies: null,
          isAutoDispose: true,
        );

  ApplyToJobControllerProvider call(
    String jobId,
  ) =>
      ApplyToJobControllerProvider._(argument: jobId, from: this);

  @override
  String toString() => r'applyToJobControllerProvider';
}

abstract class _$ApplyToJobController extends $AsyncNotifier<ApplicationDto?> {
  late final _$args = ref.$arg as String;
  String get jobId => _$args;

  FutureOr<ApplicationDto?> build(
    String jobId,
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
