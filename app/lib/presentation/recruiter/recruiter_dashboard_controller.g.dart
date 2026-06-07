// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'recruiter_dashboard_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(RecruiterDashboardController)
final recruiterDashboardControllerProvider =
    RecruiterDashboardControllerProvider._();

final class RecruiterDashboardControllerProvider extends $AsyncNotifierProvider<
    RecruiterDashboardController, RecruiterDashboardSummary> {
  RecruiterDashboardControllerProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'recruiterDashboardControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$recruiterDashboardControllerHash();

  @$internal
  @override
  RecruiterDashboardController create() => RecruiterDashboardController();
}

String _$recruiterDashboardControllerHash() =>
    r'e3f0026939f9f2c9231c092800832f1d3c6bae58';

abstract class _$RecruiterDashboardController
    extends $AsyncNotifier<RecruiterDashboardSummary> {
  FutureOr<RecruiterDashboardSummary> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<AsyncValue<RecruiterDashboardSummary>,
        RecruiterDashboardSummary>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<AsyncValue<RecruiterDashboardSummary>,
            RecruiterDashboardSummary>,
        AsyncValue<RecruiterDashboardSummary>,
        Object?,
        Object?>;
    element.handleCreate(ref, build);
  }
}
