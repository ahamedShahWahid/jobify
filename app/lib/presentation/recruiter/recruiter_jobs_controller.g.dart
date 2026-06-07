// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'recruiter_jobs_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(RecruiterJobsController)
final recruiterJobsControllerProvider = RecruiterJobsControllerFamily._();

final class RecruiterJobsControllerProvider extends $AsyncNotifierProvider<
    RecruiterJobsController, RecruiterJobsState> {
  RecruiterJobsControllerProvider._(
      {required RecruiterJobsControllerFamily super.from,
      required bool super.argument})
      : super(
          retry: null,
          name: r'recruiterJobsControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$recruiterJobsControllerHash();

  @override
  String toString() {
    return r'recruiterJobsControllerProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  RecruiterJobsController create() => RecruiterJobsController();

  @override
  bool operator ==(Object other) {
    return other is RecruiterJobsControllerProvider &&
        other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$recruiterJobsControllerHash() =>
    r'a089e374344c792616a771a1c232cf46717ffe34';

final class RecruiterJobsControllerFamily extends $Family
    with
        $ClassFamilyOverride<
            RecruiterJobsController,
            AsyncValue<RecruiterJobsState>,
            RecruiterJobsState,
            FutureOr<RecruiterJobsState>,
            bool> {
  RecruiterJobsControllerFamily._()
      : super(
          retry: null,
          name: r'recruiterJobsControllerProvider',
          dependencies: null,
          $allTransitiveDependencies: null,
          isAutoDispose: true,
        );

  RecruiterJobsControllerProvider call(
    bool includeClosed,
  ) =>
      RecruiterJobsControllerProvider._(argument: includeClosed, from: this);

  @override
  String toString() => r'recruiterJobsControllerProvider';
}

abstract class _$RecruiterJobsController
    extends $AsyncNotifier<RecruiterJobsState> {
  late final _$args = ref.$arg as bool;
  bool get includeClosed => _$args;

  FutureOr<RecruiterJobsState> build(
    bool includeClosed,
  );
  @$mustCallSuper
  @override
  void runBuild() {
    final ref =
        this.ref as $Ref<AsyncValue<RecruiterJobsState>, RecruiterJobsState>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<AsyncValue<RecruiterJobsState>, RecruiterJobsState>,
        AsyncValue<RecruiterJobsState>,
        Object?,
        Object?>;
    element.handleCreate(
        ref,
        () => build(
              _$args,
            ));
  }
}
