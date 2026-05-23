import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import 'package:kpa_app/presentation/applications/applications_controller.dart';
import 'package:kpa_app/presentation/routing/routes.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';
import 'package:kpa_app/presentation/widgets/async_value_widget.dart';
import 'package:kpa_app/presentation/widgets/kpa_empty_state.dart';
import 'package:kpa_app/presentation/widgets/kpa_loading_view.dart';

final _dateFormat = DateFormat.yMMMMd();

class ApplicationsScreen extends ConsumerStatefulWidget {
  const ApplicationsScreen({super.key});
  @override
  ConsumerState<ApplicationsScreen> createState() =>
      _ApplicationsScreenState();
}

class _ApplicationsScreenState
    extends ConsumerState<ApplicationsScreen> {
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.pixels >=
          _scroll.position.maxScrollExtent - 200) {
        ref.read(applicationsControllerProvider.notifier).loadMore();
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
    final value = ref.watch(applicationsControllerProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Applications')),
      body: AsyncValueWidget<ApplicationsState>(
        value: value,
        onRetry: () =>
            ref.read(applicationsControllerProvider.notifier).refresh(),
        isEmpty: (s) => s.items.isEmpty,
        empty: () => KpaEmptyState(
          headline: 'No applications yet',
          body: 'Browse the feed and apply to roles you like.',
          icon: Icons.assignment_outlined,
          primaryAction: FilledButton(
            onPressed: () => context.go(Routes.feed),
            child: const Text('Browse the feed'),
          ),
        ),
        data: (s) => RefreshIndicator(
          onRefresh: () => ref
              .read(applicationsControllerProvider.notifier)
              .refresh(),
          child: ListView.separated(
            controller: _scroll,
            padding: const EdgeInsets.all(KpaSpacing.lg),
            itemCount: s.items.length + 1,
            separatorBuilder: (_, __) =>
                const SizedBox(height: KpaSpacing.md),
            itemBuilder: (context, i) {
              if (i == s.items.length) {
                if (s.isLoadingMore) {
                  return const Padding(
                    padding: EdgeInsets.all(KpaSpacing.lg),
                    child: KpaLoadingView(),
                  );
                }
                return const SizedBox.shrink();
              }
              final item = s.items[i];
              return Card(
                child: InkWell(
                  onTap: () => context.go(
                    '${Routes.applications}/jobs/${item.job.id}',
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(KpaSpacing.lg),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                item.employer.name,
                                style:
                                    Theme.of(context).textTheme.labelLarge,
                              ),
                            ),
                            _StatusPill(status: item.application.status),
                          ],
                        ),
                        const SizedBox(height: KpaSpacing.sm),
                        Text(
                          item.job.title,
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: KpaSpacing.xs),
                        Text(
                          () {
                            final isWithdrawn = item.application.status ==
                                'withdrawn';
                            final whenDate = isWithdrawn
                                ? item.application.withdrawnAt!
                                : item.application.createdAt;
                            final whenLabel = isWithdrawn
                                ? 'Withdrawn ${_dateFormat.format(whenDate)}'
                                : 'Applied ${_dateFormat.format(whenDate)}';
                            return whenLabel;
                          }(),
                          style: Theme.of(context)
                              .textTheme
                              .bodySmall
                              ?.copyWith(
                                color: Theme.of(context)
                                    .colorScheme
                                    .onSurfaceVariant,
                              ),
                        ),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill({required this.status});
  final String status;
  @override
  Widget build(BuildContext context) {
    final c = Theme.of(context);
    final (label, bg, fg) = status == 'applied'
        ? (
            'Applied',
            c.colorScheme.primaryContainer,
            c.colorScheme.onPrimaryContainer,
          )
        : (
            'Withdrawn',
            c.colorScheme.surfaceContainerHighest,
            c.colorScheme.onSurfaceVariant,
          );
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: KpaSpacing.sm,
        vertical: KpaSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: c.textTheme.labelSmall?.copyWith(color: fg),
      ),
    );
  }
}
