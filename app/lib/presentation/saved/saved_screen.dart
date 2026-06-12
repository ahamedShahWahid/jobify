import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/data/jobs/job_status.dart';
import 'package:jobify_app/presentation/feed/feed_item_card.dart';
import 'package:jobify_app/presentation/routing/routes.dart';
import 'package:jobify_app/presentation/saved/saved_controller.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';
import 'package:jobify_app/presentation/widgets/async_value_widget.dart';
import 'package:jobify_app/presentation/widgets/jobify_empty_state.dart';
import 'package:jobify_app/presentation/widgets/jobify_loading_view.dart';

class SavedScreen extends ConsumerStatefulWidget {
  const SavedScreen({super.key});
  @override
  ConsumerState<SavedScreen> createState() => _SavedScreenState();
}

class _SavedScreenState extends ConsumerState<SavedScreen> {
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.pixels >= _scroll.position.maxScrollExtent - 200) {
        ref.read(savedControllerProvider.notifier).loadMore();
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
    final value = ref.watch(savedControllerProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Saved')),
      body: AsyncValueWidget<SavedState>(
        value: value,
        onRetry: () => ref.read(savedControllerProvider.notifier).refresh(),
        isEmpty: (s) => s.items.isEmpty,
        empty: () => const JobifyEmptyState(
          headline: 'Nothing saved yet',
          body: 'Tap the heart on any job to save it for later.',
          icon: Icons.bookmark_outline,
        ),
        data: (s) => RefreshIndicator(
          onRefresh: () => ref.read(savedControllerProvider.notifier).refresh(),
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
                return const SizedBox.shrink();
              }
              final item = s.items[i];
              return FeedItemCard(
                job: item.job,
                employer: item.employer,
                match: item.match,
                explanation: item.match?.explanation,
                showScore: item.job.status == JobStatus.open,
                onTap: () => context.go('${Routes.saved}/jobs/${item.job.id}'),
              );
            },
          ),
        ),
      ),
    );
  }
}
