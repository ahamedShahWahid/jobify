// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'match_feedback_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Rates / clears the match rating from job detail.
///
/// DELIBERATE exception to the "never invalidate the feed on mutation" rule
/// (app/CLAUDE.md): a down-rate changes feed MEMBERSHIP server-side, so the
/// kept-alive feed list must refetch or it keeps showing the hidden job.

@ProviderFor(MatchFeedbackController)
final matchFeedbackControllerProvider = MatchFeedbackControllerFamily._();

/// Rates / clears the match rating from job detail.
///
/// DELIBERATE exception to the "never invalidate the feed on mutation" rule
/// (app/CLAUDE.md): a down-rate changes feed MEMBERSHIP server-side, so the
/// kept-alive feed list must refetch or it keeps showing the hidden job.
final class MatchFeedbackControllerProvider
    extends $AsyncNotifierProvider<MatchFeedbackController, void> {
  /// Rates / clears the match rating from job detail.
  ///
  /// DELIBERATE exception to the "never invalidate the feed on mutation" rule
  /// (app/CLAUDE.md): a down-rate changes feed MEMBERSHIP server-side, so the
  /// kept-alive feed list must refetch or it keeps showing the hidden job.
  MatchFeedbackControllerProvider._(
      {required MatchFeedbackControllerFamily super.from,
      required String super.argument})
      : super(
          retry: null,
          name: r'matchFeedbackControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$matchFeedbackControllerHash();

  @override
  String toString() {
    return r'matchFeedbackControllerProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  MatchFeedbackController create() => MatchFeedbackController();

  @override
  bool operator ==(Object other) {
    return other is MatchFeedbackControllerProvider &&
        other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$matchFeedbackControllerHash() =>
    r'4591f139e42bb1b60e7d89fe97a31db7514504d0';

/// Rates / clears the match rating from job detail.
///
/// DELIBERATE exception to the "never invalidate the feed on mutation" rule
/// (app/CLAUDE.md): a down-rate changes feed MEMBERSHIP server-side, so the
/// kept-alive feed list must refetch or it keeps showing the hidden job.

final class MatchFeedbackControllerFamily extends $Family
    with
        $ClassFamilyOverride<MatchFeedbackController, AsyncValue<void>, void,
            FutureOr<void>, String> {
  MatchFeedbackControllerFamily._()
      : super(
          retry: null,
          name: r'matchFeedbackControllerProvider',
          dependencies: null,
          $allTransitiveDependencies: null,
          isAutoDispose: true,
        );

  /// Rates / clears the match rating from job detail.
  ///
  /// DELIBERATE exception to the "never invalidate the feed on mutation" rule
  /// (app/CLAUDE.md): a down-rate changes feed MEMBERSHIP server-side, so the
  /// kept-alive feed list must refetch or it keeps showing the hidden job.

  MatchFeedbackControllerProvider call(
    String jobId,
  ) =>
      MatchFeedbackControllerProvider._(argument: jobId, from: this);

  @override
  String toString() => r'matchFeedbackControllerProvider';
}

/// Rates / clears the match rating from job detail.
///
/// DELIBERATE exception to the "never invalidate the feed on mutation" rule
/// (app/CLAUDE.md): a down-rate changes feed MEMBERSHIP server-side, so the
/// kept-alive feed list must refetch or it keeps showing the hidden job.

abstract class _$MatchFeedbackController extends $AsyncNotifier<void> {
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
