// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'job_form_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Full job detail for the edit form — list rows omit description
/// (PERF-09), so EditJobResolver always resolves through here rather than
/// trusting whatever row it was reached with (a passed `extra` or a cold
/// deep-link). autoDispose: only needed transiently while opening the form.

@ProviderFor(recruiterJobDetail)
final recruiterJobDetailProvider = RecruiterJobDetailFamily._();

/// Full job detail for the edit form — list rows omit description
/// (PERF-09), so EditJobResolver always resolves through here rather than
/// trusting whatever row it was reached with (a passed `extra` or a cold
/// deep-link). autoDispose: only needed transiently while opening the form.

final class RecruiterJobDetailProvider
    extends
        $FunctionalProvider<
          AsyncValue<RecruiterJobDto>,
          RecruiterJobDto,
          FutureOr<RecruiterJobDto>
        >
    with $FutureModifier<RecruiterJobDto>, $FutureProvider<RecruiterJobDto> {
  /// Full job detail for the edit form — list rows omit description
  /// (PERF-09), so EditJobResolver always resolves through here rather than
  /// trusting whatever row it was reached with (a passed `extra` or a cold
  /// deep-link). autoDispose: only needed transiently while opening the form.
  RecruiterJobDetailProvider._({
    required RecruiterJobDetailFamily super.from,
    required String super.argument,
  }) : super(
         retry: null,
         name: r'recruiterJobDetailProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$recruiterJobDetailHash();

  @override
  String toString() {
    return r'recruiterJobDetailProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  $FutureProviderElement<RecruiterJobDto> $createElement(
    $ProviderPointer pointer,
  ) => $FutureProviderElement(pointer);

  @override
  FutureOr<RecruiterJobDto> create(Ref ref) {
    final argument = this.argument as String;
    return recruiterJobDetail(ref, argument);
  }

  @override
  bool operator ==(Object other) {
    return other is RecruiterJobDetailProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$recruiterJobDetailHash() =>
    r'9b3fd58ba3fe8fb8ec0b50f4903c8a71f73c7dc4';

/// Full job detail for the edit form — list rows omit description
/// (PERF-09), so EditJobResolver always resolves through here rather than
/// trusting whatever row it was reached with (a passed `extra` or a cold
/// deep-link). autoDispose: only needed transiently while opening the form.

final class RecruiterJobDetailFamily extends $Family
    with $FunctionalFamilyOverride<FutureOr<RecruiterJobDto>, String> {
  RecruiterJobDetailFamily._()
    : super(
        retry: null,
        name: r'recruiterJobDetailProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// Full job detail for the edit form — list rows omit description
  /// (PERF-09), so EditJobResolver always resolves through here rather than
  /// trusting whatever row it was reached with (a passed `extra` or a cold
  /// deep-link). autoDispose: only needed transiently while opening the form.

  RecruiterJobDetailProvider call(String jobId) =>
      RecruiterJobDetailProvider._(argument: jobId, from: this);

  @override
  String toString() => r'recruiterJobDetailProvider';
}

@ProviderFor(JobFormController)
final jobFormControllerProvider = JobFormControllerProvider._();

final class JobFormControllerProvider
    extends $AsyncNotifierProvider<JobFormController, RecruiterJobDto?> {
  JobFormControllerProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'jobFormControllerProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$jobFormControllerHash();

  @$internal
  @override
  JobFormController create() => JobFormController();
}

String _$jobFormControllerHash() => r'1c5ac61f75418d2bcbf4c01606e414661bb52fd7';

abstract class _$JobFormController extends $AsyncNotifier<RecruiterJobDto?> {
  FutureOr<RecruiterJobDto?> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref =
        this.ref as $Ref<AsyncValue<RecruiterJobDto?>, RecruiterJobDto?>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<AsyncValue<RecruiterJobDto?>, RecruiterJobDto?>,
              AsyncValue<RecruiterJobDto?>,
              Object?,
              Object?
            >;
    element.handleCreate(ref, build);
  }
}
