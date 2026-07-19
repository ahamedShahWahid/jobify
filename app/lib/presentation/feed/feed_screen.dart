import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/feed/feed_visit_repository_impl.dart';
import 'package:jobify_app/presentation/feed/feed_controller.dart';
import 'package:jobify_app/presentation/feed/feed_item_card.dart';
import 'package:jobify_app/presentation/feed/feed_summary_controller.dart';
import 'package:jobify_app/presentation/feed/feed_summary_row.dart';
import 'package:jobify_app/presentation/routing/routes.dart';
import 'package:jobify_app/presentation/theme/jobify_colors.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';
import 'package:jobify_app/presentation/widgets/arrive.dart';
import 'package:jobify_app/presentation/widgets/async_value_widget.dart';
import 'package:jobify_app/presentation/widgets/bold_header.dart';
import 'package:jobify_app/presentation/widgets/jobify_empty_state.dart';
import 'package:jobify_app/presentation/widgets/jobify_loading_view.dart';

class FeedScreen extends ConsumerStatefulWidget {
  const FeedScreen({super.key});
  @override
  ConsumerState<FeedScreen> createState() => _FeedScreenState();
}

class _FeedScreenState extends ConsumerState<FeedScreen> {
  final _scroll = ScrollController();
  DateTime? _lastSeenAt;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.pixels >= _scroll.position.maxScrollExtent - 200) {
        ref.read(feedControllerProvider.notifier).loadMore();
      }
    });
    unawaited(_stampVisit());
  }

  /// One-shot per screen mount — NOT tied to feedControllerProvider rebuilds
  /// (refresh/loadMore also emit new AsyncValue.data, which would otherwise
  /// re-stamp the visit and make the count only ever reflect the last
  /// pull-to-refresh instead of the last time the app was actually opened).
  Future<void> _stampVisit() async {
    final repo = ref.read(feedVisitRepositoryProvider);
    final prev = await repo.getLastSeenAt();
    if (mounted) setState(() => _lastSeenAt = prev);
    await repo.setLastSeenAt(DateTime.now());
  }

  /// Refreshes the job list AND the home-summary tiles together — both the
  /// header refresh button and pull-to-refresh previously only called
  /// FeedController.refresh(), leaving the Applications/Saved summary tiles
  /// stale until a mutation elsewhere (apply/save/unsave/withdraw)
  /// invalidated feedSummaryControllerProvider on its own.
  Future<void> _refreshAll() async {
    await Future.wait([
      ref.read(feedControllerProvider.notifier).refresh(),
      ref.read(feedSummaryControllerProvider.notifier).refresh(),
    ]);
  }

  /// Only counts matches within whatever FeedController has currently
  /// loaded (first page, ordered by match score, not recency) — a
  /// documented MVP approximation, not a global truth.
  int _newMatchesCount(List<FeedItemDto> items) {
    final lastSeenAt = _lastSeenAt;
    if (lastSeenAt == null) return 0;
    return items
        .where((i) => i.match.surfacedAt?.isAfter(lastSeenAt) ?? false)
        .length;
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _rateUp(String jobId) async {
    try {
      await ref.read(feedControllerProvider.notifier).rateUp(jobId);
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Couldn't save your rating")),
      );
    }
  }

  Future<void> _rateDown(String jobId) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await ref.read(feedControllerProvider.notifier).rateDown(jobId);
    } catch (_) {
      messenger.showSnackBar(
        const SnackBar(content: Text("Couldn't save your rating")),
      );
      return;
    }
    messenger.showSnackBar(
      SnackBar(
        content: const Text('Hidden from your feed'),
        action: SnackBarAction(
          label: 'Undo',
          onPressed: () =>
              ref.read(feedControllerProvider.notifier).undoDown(jobId),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final value = ref.watch(feedControllerProvider);
    final newCount =
        value.value != null ? _newMatchesCount(value.value!.items) : 0;
    return BoldScaffold(
      header: BoldHeader(
        title: 'For you',
        subtitle: 'Roles matched to your profile',
        trailing: IconButton(
          icon: const Icon(Icons.refresh),
          tooltip: 'Refresh',
          onPressed: () => unawaited(_refreshAll()),
        ),
      ),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(
              JobifySpacing.lg,
              JobifySpacing.lg,
              JobifySpacing.lg,
              0,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (newCount > 0) _NewMatchesHeadline(count: newCount),
                // FeedSummaryRow's Row uses CrossAxisAlignment.stretch, which
                // needs a bounded height to stretch its tiles against. Nested
                // two Columns deep here, it would otherwise inherit an
                // unbounded height from this screen's outer Column and crash
                // ("BoxConstraints forces an infinite height").
                // IntrinsicHeight resolves a concrete height first.
                const IntrinsicHeight(child: FeedSummaryRow()),
              ],
            ),
          ),
          Expanded(
            child: AsyncValueWidget<FeedState>(
              value: value,
              onRetry: () =>
                  ref.read(feedControllerProvider.notifier).refresh(),
              isEmpty: (s) => s.items.isEmpty,
              empty: () => const JobifyEmptyState(
                headline: "We're still looking for matches",
                body: 'Upload a resume to help us find you better roles.',
                icon: Icons.search_off,
              ),
              data: (s) => RefreshIndicator(
                onRefresh: _refreshAll,
                child: ListView.separated(
                  controller: _scroll,
                  padding: const EdgeInsets.all(JobifySpacing.lg),
                  itemCount: s.items.length + 1,
                  separatorBuilder: (_, __) =>
                      const SizedBox(height: JobifySpacing.md),
                  itemBuilder: (context, i) {
                    if (i == s.items.length) {
                      if (s.isLoadingMore) {
                        return const Padding(
                          padding: EdgeInsets.all(JobifySpacing.lg),
                          child: JobifyLoadingView(),
                        );
                      }
                      if (!s.hasMore) {
                        return Padding(
                          padding: const EdgeInsets.all(JobifySpacing.lg),
                          child: Center(
                            child: Text(
                              "You're all caught up",
                              style: Theme.of(context)
                                  .textTheme
                                  .bodySmall
                                  ?.copyWith(
                                    color: Theme.of(context)
                                        .colorScheme
                                        .onSurfaceVariant,
                                  ),
                            ),
                          ),
                        );
                      }
                      return const SizedBox.shrink();
                    }
                    final item = s.items[i];
                    return Arrive(
                      index: i,
                      child: FeedItemCard(
                        job: item.job,
                        employer: item.employer,
                        onTap: () =>
                            context.go('${Routes.feed}/jobs/${item.job.id}'),
                        match: item.match,
                        explanation: item.match.explanation,
                        myFeedback: item.match.myFeedback,
                        onThumbUp: () => _rateUp(item.job.id),
                        onThumbDown: () => _rateDown(item.job.id),
                      ),
                    );
                  },
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _NewMatchesHeadline extends StatelessWidget {
  const _NewMatchesHeadline({required this.count});
  final int count;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final brand =
        isDark ? JobifyColors.brandBlueDark : JobifyColors.brandBlueLight;
    return Padding(
      padding: const EdgeInsets.only(bottom: JobifySpacing.md),
      child: Text(
        count == 1
            ? '1 new match since your last visit'
            : '$count new matches since your last visit',
        style: theme.textTheme.titleMedium?.copyWith(color: brand),
      ),
    );
  }
}
