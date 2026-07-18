// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'unsave_job_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(UnsaveJobController)
final unsaveJobControllerProvider = UnsaveJobControllerFamily._();

final class UnsaveJobControllerProvider
    extends $AsyncNotifierProvider<UnsaveJobController, void> {
  UnsaveJobControllerProvider._(
      {required UnsaveJobControllerFamily super.from,
      required String super.argument})
      : super(
          retry: null,
          name: r'unsaveJobControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$unsaveJobControllerHash();

  @override
  String toString() {
    return r'unsaveJobControllerProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  UnsaveJobController create() => UnsaveJobController();

  @override
  bool operator ==(Object other) {
    return other is UnsaveJobControllerProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$unsaveJobControllerHash() =>
    r'06acec1d8a52e758106451f5d6598d04bd68ba48';

final class UnsaveJobControllerFamily extends $Family
    with
        $ClassFamilyOverride<UnsaveJobController, AsyncValue<void>, void,
            FutureOr<void>, String> {
  UnsaveJobControllerFamily._()
      : super(
          retry: null,
          name: r'unsaveJobControllerProvider',
          dependencies: null,
          $allTransitiveDependencies: null,
          isAutoDispose: true,
        );

  UnsaveJobControllerProvider call(
    String jobId,
  ) =>
      UnsaveJobControllerProvider._(argument: jobId, from: this);

  @override
  String toString() => r'unsaveJobControllerProvider';
}

abstract class _$UnsaveJobController extends $AsyncNotifier<void> {
  late final _$args = ref.$arg as String;
  String get jobId => _$args;

  FutureOr<void> build(
    String jobId,
  );
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<AsyncValue<void>, void>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<AsyncValue<void>, void>,
        AsyncValue<void>,
        Object?,
        Object?>;
    element.handleCreate(
        ref,
        () => build(
              _$args,
            ));
  }
}
