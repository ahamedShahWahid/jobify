// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'job_form_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

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

String _$jobFormControllerHash() => r'e94a234d650478e504362b0fbcf3893b25d8ca27';

abstract class _$JobFormController extends $AsyncNotifier<RecruiterJobDto?> {
  FutureOr<RecruiterJobDto?> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref =
        this.ref as $Ref<AsyncValue<RecruiterJobDto?>, RecruiterJobDto?>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<AsyncValue<RecruiterJobDto?>, RecruiterJobDto?>,
        AsyncValue<RecruiterJobDto?>,
        Object?,
        Object?>;
    element.handleCreate(ref, build);
  }
}
