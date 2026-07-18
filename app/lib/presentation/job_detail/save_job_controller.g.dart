// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'save_job_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(SaveJobController)
final saveJobControllerProvider = SaveJobControllerFamily._();

final class SaveJobControllerProvider
    extends $AsyncNotifierProvider<SaveJobController, SavedJobDto?> {
  SaveJobControllerProvider._(
      {required SaveJobControllerFamily super.from,
      required String super.argument})
      : super(
          retry: null,
          name: r'saveJobControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$saveJobControllerHash();

  @override
  String toString() {
    return r'saveJobControllerProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  SaveJobController create() => SaveJobController();

  @override
  bool operator ==(Object other) {
    return other is SaveJobControllerProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$saveJobControllerHash() => r'61e5d9843616c9170cc0366e4a2918b8d7178b3e';

final class SaveJobControllerFamily extends $Family
    with
        $ClassFamilyOverride<SaveJobController, AsyncValue<SavedJobDto?>,
            SavedJobDto?, FutureOr<SavedJobDto?>, String> {
  SaveJobControllerFamily._()
      : super(
          retry: null,
          name: r'saveJobControllerProvider',
          dependencies: null,
          $allTransitiveDependencies: null,
          isAutoDispose: true,
        );

  SaveJobControllerProvider call(
    String jobId,
  ) =>
      SaveJobControllerProvider._(argument: jobId, from: this);

  @override
  String toString() => r'saveJobControllerProvider';
}

abstract class _$SaveJobController extends $AsyncNotifier<SavedJobDto?> {
  late final _$args = ref.$arg as String;
  String get jobId => _$args;

  FutureOr<SavedJobDto?> build(
    String jobId,
  );
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<AsyncValue<SavedJobDto?>, SavedJobDto?>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<AsyncValue<SavedJobDto?>, SavedJobDto?>,
        AsyncValue<SavedJobDto?>,
        Object?,
        Object?>;
    element.handleCreate(
        ref,
        () => build(
              _$args,
            ));
  }
}
