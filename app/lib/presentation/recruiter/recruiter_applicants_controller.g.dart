// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'recruiter_applicants_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(RecruiterApplicantsController)
final recruiterApplicantsControllerProvider =
    RecruiterApplicantsControllerFamily._();

final class RecruiterApplicantsControllerProvider
    extends $AsyncNotifierProvider<RecruiterApplicantsController,
        RecruiterApplicantsState> {
  RecruiterApplicantsControllerProvider._(
      {required RecruiterApplicantsControllerFamily super.from,
      required String super.argument})
      : super(
          retry: null,
          name: r'recruiterApplicantsControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$recruiterApplicantsControllerHash();

  @override
  String toString() {
    return r'recruiterApplicantsControllerProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  RecruiterApplicantsController create() => RecruiterApplicantsController();

  @override
  bool operator ==(Object other) {
    return other is RecruiterApplicantsControllerProvider &&
        other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$recruiterApplicantsControllerHash() =>
    r'ec8b38d6c25c201bdb327dc0e08a00befd47e505';

final class RecruiterApplicantsControllerFamily extends $Family
    with
        $ClassFamilyOverride<
            RecruiterApplicantsController,
            AsyncValue<RecruiterApplicantsState>,
            RecruiterApplicantsState,
            FutureOr<RecruiterApplicantsState>,
            String> {
  RecruiterApplicantsControllerFamily._()
      : super(
          retry: null,
          name: r'recruiterApplicantsControllerProvider',
          dependencies: null,
          $allTransitiveDependencies: null,
          isAutoDispose: true,
        );

  RecruiterApplicantsControllerProvider call(
    String jobId,
  ) =>
      RecruiterApplicantsControllerProvider._(argument: jobId, from: this);

  @override
  String toString() => r'recruiterApplicantsControllerProvider';
}

abstract class _$RecruiterApplicantsController
    extends $AsyncNotifier<RecruiterApplicantsState> {
  late final _$args = ref.$arg as String;
  String get jobId => _$args;

  FutureOr<RecruiterApplicantsState> build(
    String jobId,
  );
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref
        as $Ref<AsyncValue<RecruiterApplicantsState>, RecruiterApplicantsState>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<AsyncValue<RecruiterApplicantsState>,
            RecruiterApplicantsState>,
        AsyncValue<RecruiterApplicantsState>,
        Object?,
        Object?>;
    element.handleCreate(
        ref,
        () => build(
              _$args,
            ));
  }
}
