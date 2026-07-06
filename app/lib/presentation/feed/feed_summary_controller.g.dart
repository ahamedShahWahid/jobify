// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'feed_summary_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(FeedSummaryController)
final feedSummaryControllerProvider = FeedSummaryControllerProvider._();

final class FeedSummaryControllerProvider
    extends $AsyncNotifierProvider<FeedSummaryController, FeedSummary> {
  FeedSummaryControllerProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'feedSummaryControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$feedSummaryControllerHash();

  @$internal
  @override
  FeedSummaryController create() => FeedSummaryController();
}

String _$feedSummaryControllerHash() =>
    r'6a8b53615153a344727f6428c94a02ecf17f9577';

abstract class _$FeedSummaryController extends $AsyncNotifier<FeedSummary> {
  FutureOr<FeedSummary> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<AsyncValue<FeedSummary>, FeedSummary>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<AsyncValue<FeedSummary>, FeedSummary>,
        AsyncValue<FeedSummary>,
        Object?,
        Object?>;
    element.handleCreate(ref, build);
  }
}
