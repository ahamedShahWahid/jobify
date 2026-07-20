// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'application_timeline_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Stage-change events for one application. Family keyed by applicationId;
/// consumed by `_ApplicationTimeline` in job_detail_screen.dart.

@ProviderFor(applicationTimeline)
final applicationTimelineProvider = ApplicationTimelineFamily._();

/// Stage-change events for one application. Family keyed by applicationId;
/// consumed by `_ApplicationTimeline` in job_detail_screen.dart.

final class ApplicationTimelineProvider extends $FunctionalProvider<
        AsyncValue<List<StageEventDto>>,
        List<StageEventDto>,
        FutureOr<List<StageEventDto>>>
    with
        $FutureModifier<List<StageEventDto>>,
        $FutureProvider<List<StageEventDto>> {
  /// Stage-change events for one application. Family keyed by applicationId;
  /// consumed by `_ApplicationTimeline` in job_detail_screen.dart.
  ApplicationTimelineProvider._(
      {required ApplicationTimelineFamily super.from,
      required String super.argument})
      : super(
          retry: null,
          name: r'applicationTimelineProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$applicationTimelineHash();

  @override
  String toString() {
    return r'applicationTimelineProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  $FutureProviderElement<List<StageEventDto>> $createElement(
          $ProviderPointer pointer) =>
      $FutureProviderElement(pointer);

  @override
  FutureOr<List<StageEventDto>> create(Ref ref) {
    final argument = this.argument as String;
    return applicationTimeline(
      ref,
      argument,
    );
  }

  @override
  bool operator ==(Object other) {
    return other is ApplicationTimelineProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$applicationTimelineHash() =>
    r'5e5a9e2a42fc7dc8425023ed0e06320cee2a5046';

/// Stage-change events for one application. Family keyed by applicationId;
/// consumed by `_ApplicationTimeline` in job_detail_screen.dart.

final class ApplicationTimelineFamily extends $Family
    with $FunctionalFamilyOverride<FutureOr<List<StageEventDto>>, String> {
  ApplicationTimelineFamily._()
      : super(
          retry: null,
          name: r'applicationTimelineProvider',
          dependencies: null,
          $allTransitiveDependencies: null,
          isAutoDispose: true,
        );

  /// Stage-change events for one application. Family keyed by applicationId;
  /// consumed by `_ApplicationTimeline` in job_detail_screen.dart.

  ApplicationTimelineProvider call(
    String applicationId,
  ) =>
      ApplicationTimelineProvider._(argument: applicationId, from: this);

  @override
  String toString() => r'applicationTimelineProvider';
}
