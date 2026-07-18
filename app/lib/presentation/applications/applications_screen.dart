import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/core/format/date_formats.dart';
import 'package:jobify_app/data/jobs/application_status.dart';
import 'package:jobify_app/presentation/applications/applications_controller.dart';
import 'package:jobify_app/presentation/routing/routes.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';
import 'package:jobify_app/presentation/theme/jobify_typography.dart';
import 'package:jobify_app/presentation/widgets/async_value_widget.dart';
import 'package:jobify_app/presentation/widgets/bold_header.dart';
import 'package:jobify_app/presentation/widgets/jobify_empty_state.dart';
import 'package:jobify_app/presentation/widgets/jobify_loading_view.dart';

class ApplicationsScreen extends ConsumerStatefulWidget {
  const ApplicationsScreen({super.key});
  @override
  ConsumerState<ApplicationsScreen> createState() => _ApplicationsScreenState();
}

class _ApplicationsScreenState extends ConsumerState<ApplicationsScreen> {
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.pixels >= _scroll.position.maxScrollExtent - 200) {
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
    return BoldScaffold(
      header: const BoldHeader(
        title: 'Applications',
        subtitle: 'Roles you applied to',
      ),
      child: AsyncValueWidget<ApplicationsState>(
        value: value,
        onRetry: () =>
            ref.read(applicationsControllerProvider.notifier).refresh(),
        isEmpty: (s) => s.items.isEmpty,
        empty: () => JobifyEmptyState(
          headline: 'No applications yet',
          body: 'Browse the feed and apply to roles you like.',
          icon: Icons.assignment_outlined,
          primaryAction: FilledButton(
            onPressed: () => context.go(Routes.feed),
            child: const Text('Browse the feed'),
          ),
        ),
        data: (s) => RefreshIndicator(
          onRefresh: () =>
              ref.read(applicationsControllerProvider.notifier).refresh(),
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
              return Card(
                child: InkWell(
                  onTap: () => context.go(
                    '${Routes.applications}/jobs/${item.job.id}',
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(JobifySpacing.lg),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                item.employer.name,
                                style: Theme.of(context).textTheme.labelLarge,
                              ),
                            ),
                            _StatusPill(status: item.application.status),
                          ],
                        ),
                        const SizedBox(height: JobifySpacing.sm),
                        Text(
                          item.job.title,
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: JobifySpacing.xs),
                        Text(
                          () {
                            final isWithdrawn = item.application.status ==
                                ApplicationStatus.withdrawn;
                            final whenDate = isWithdrawn
                                ? item.application.updatedAt
                                : item.application.createdAt;
                            final when = jobifyLongDateFormat.format(whenDate);
                            return isWithdrawn
                                ? 'Withdrawn $when'
                                : 'Applied $when';
                          }(),
                          style: JobifyTypography.mono(
                            fontSize: 12,
                            color:
                                Theme.of(context).colorScheme.onSurfaceVariant,
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
  final ApplicationStatus status;
  @override
  Widget build(BuildContext context) {
    final c = Theme.of(context);
    final (label, bg, fg) = status == ApplicationStatus.applied
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
        horizontal: JobifySpacing.sm,
        vertical: JobifySpacing.xs,
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
