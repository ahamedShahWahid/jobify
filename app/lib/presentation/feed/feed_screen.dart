import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/presentation/feed/feed_controller.dart';
import 'package:jobify_app/presentation/feed/feed_item_card.dart';
import 'package:jobify_app/presentation/routing/routes.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';
import 'package:jobify_app/presentation/widgets/async_value_widget.dart';
import 'package:jobify_app/presentation/widgets/jobify_empty_state.dart';
import 'package:jobify_app/presentation/widgets/jobify_loading_view.dart';

class FeedScreen extends ConsumerStatefulWidget {
  const FeedScreen({super.key});
  @override
  ConsumerState<FeedScreen> createState() => _FeedScreenState();
}

class _FeedScreenState extends ConsumerState<FeedScreen> {
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.pixels >= _scroll.position.maxScrollExtent - 200) {
        ref.read(feedControllerProvider.notifier).loadMore();
      }
    });
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final value = ref.watch(feedControllerProvider);
    return Scaffold(
      appBar: AppBar(
        title: const Text('For you'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () =>
                ref.read(feedControllerProvider.notifier).refresh(),
          ),
        ],
      ),
      body: AsyncValueWidget<FeedState>(
        value: value,
        onRetry: () => ref.read(feedControllerProvider.notifier).refresh(),
        isEmpty: (s) => s.items.isEmpty,
        empty: () => const JobifyEmptyState(
          headline: "We're still looking for matches",
          body: 'Upload a resume to help us find you better roles.',
          icon: Icons.search_off,
        ),
        data: (s) => RefreshIndicator(
          onRefresh: () => ref.read(feedControllerProvider.notifier).refresh(),
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
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
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
              return FeedItemCard(
                job: item.job,
                employer: item.employer,
                onTap: () => context.go('${Routes.feed}/jobs/${item.job.id}'),
                match: item.match,
                explanation: item.match.explanation,
              );
            },
          ),
        ),
      ),
    );
  }
}
