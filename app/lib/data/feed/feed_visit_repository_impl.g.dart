// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'feed_visit_repository_impl.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning

@ProviderFor(feedVisitRepository)
final feedVisitRepositoryProvider = FeedVisitRepositoryProvider._();

final class FeedVisitRepositoryProvider extends $FunctionalProvider<
    FeedVisitRepository,
    FeedVisitRepository,
    FeedVisitRepository> with $Provider<FeedVisitRepository> {
  FeedVisitRepositoryProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'feedVisitRepositoryProvider',
          isAutoDispose: false,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$feedVisitRepositoryHash();

  @$internal
  @override
  $ProviderElement<FeedVisitRepository> $createElement(
          $ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  FeedVisitRepository create(Ref ref) {
    return feedVisitRepository(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(FeedVisitRepository value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<FeedVisitRepository>(value),
    );
  }
}

String _$feedVisitRepositoryHash() =>
    r'ea21a84a17d93f0a8c05082e57bb500022f1d049';
