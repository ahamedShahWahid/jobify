// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'job_detail_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(JobDetailController)
final jobDetailControllerProvider = JobDetailControllerFamily._();

final class JobDetailControllerProvider
    extends $AsyncNotifierProvider<JobDetailController, JobDetailDto> {
  JobDetailControllerProvider._(
      {required JobDetailControllerFamily super.from,
      required String super.argument})
      : super(
          retry: null,
          name: r'jobDetailControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$jobDetailControllerHash();

  @override
  String toString() {
    return r'jobDetailControllerProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  JobDetailController create() => JobDetailController();

  @override
  bool operator ==(Object other) {
    return other is JobDetailControllerProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$jobDetailControllerHash() =>
    r'666cc2c39dd048b1c2916eeb21ff87191dbb845b';

final class JobDetailControllerFamily extends $Family
    with
        $ClassFamilyOverride<JobDetailController, AsyncValue<JobDetailDto>,
            JobDetailDto, FutureOr<JobDetailDto>, String> {
  JobDetailControllerFamily._()
      : super(
          retry: null,
          name: r'jobDetailControllerProvider',
          dependencies: null,
          $allTransitiveDependencies: null,
          isAutoDispose: true,
        );

  JobDetailControllerProvider call(
    String jobId,
  ) =>
      JobDetailControllerProvider._(argument: jobId, from: this);

  @override
  String toString() => r'jobDetailControllerProvider';
}

abstract class _$JobDetailController extends $AsyncNotifier<JobDetailDto> {
  late final _$args = ref.$arg as String;
  String get jobId => _$args;

  FutureOr<JobDetailDto> build(
    String jobId,
  );
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<AsyncValue<JobDetailDto>, JobDetailDto>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<AsyncValue<JobDetailDto>, JobDetailDto>,
        AsyncValue<JobDetailDto>,
        Object?,
        Object?>;
    element.handleCreate(
        ref,
        () => build(
              _$args,
            ));
  }
}
