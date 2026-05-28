// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'resume_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(ResumeController)
final resumeControllerProvider = ResumeControllerProvider._();

final class ResumeControllerProvider
    extends $AsyncNotifierProvider<ResumeController, ResumeDto?> {
  ResumeControllerProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'resumeControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$resumeControllerHash();

  @$internal
  @override
  ResumeController create() => ResumeController();
}

String _$resumeControllerHash() => r'65f20a3bf71f5cfbce67d4dcc74998e5557abe82';

abstract class _$ResumeController extends $AsyncNotifier<ResumeDto?> {
  FutureOr<ResumeDto?> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<AsyncValue<ResumeDto?>, ResumeDto?>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<AsyncValue<ResumeDto?>, ResumeDto?>,
        AsyncValue<ResumeDto?>,
        Object?,
        Object?>;
    element.handleCreate(ref, build);
  }
}
