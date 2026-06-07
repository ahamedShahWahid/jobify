import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:kpa_app/presentation/recruiter/recruiter_dashboard_controller.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_job_card.dart';
import 'package:kpa_app/presentation/routing/routes.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';
import 'package:kpa_app/presentation/widgets/async_value_widget.dart';
import 'package:kpa_app/presentation/widgets/kpa_empty_state.dart';

class RecruiterDashboardScreen extends ConsumerWidget {
  const RecruiterDashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final value = ref.watch(recruiterDashboardControllerProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Dashboard'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            tooltip: 'Post a job',
            onPressed: () => context.go(Routes.recruiterJobNew),
          ),
        ],
      ),
      body: AsyncValueWidget<RecruiterDashboardSummary>(
        value: value,
        onRetry: () =>
            ref.read(recruiterDashboardControllerProvider.notifier).refresh(),
        data: (summary) => RefreshIndicator(
          onRefresh: () =>
              ref.read(recruiterDashboardControllerProvider.notifier).refresh(),
          child: ListView(
            padding: const EdgeInsets.all(KpaSpacing.lg),
            children: [
              Row(
                children: [
                  Expanded(
                    child: _SummaryCard(
                      label: 'Open jobs',
                      value: '${summary.openJobs}',
                      icon: Icons.work_outline,
                    ),
                  ),
                  const SizedBox(width: KpaSpacing.md),
                  Expanded(
                    child: _SummaryCard(
                      label: 'Applicants',
                      value: '${summary.totalApplicants}',
                      icon: Icons.people_outline,
                    ),
                  ),
                  const SizedBox(width: KpaSpacing.md),
                  Expanded(
                    child: _SummaryCard(
                      label: 'Matches',
                      value: '${summary.totalSurfacedMatches}',
                      icon: Icons.bolt_outlined,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: KpaSpacing.xl),
              if (summary.recentJobs.isEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: KpaSpacing.xxl),
                  child: KpaEmptyState(
                    headline: 'No jobs yet',
                    body: 'Post your first role to start receiving applicants.',
                    icon: Icons.work_outline,
                    primaryAction: FilledButton(
                      onPressed: () => context.go(Routes.recruiterJobNew),
                      child: const Text('Post your first job'),
                    ),
                  ),
                )
              else ...[
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        'Recent jobs',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ),
                    TextButton(
                      onPressed: () => context.go(Routes.recruiterJobs),
                      child: const Text('View all'),
                    ),
                  ],
                ),
                const SizedBox(height: KpaSpacing.sm),
                for (final job in summary.recentJobs) ...[
                  RecruiterJobCard(
                    job: job,
                    onTap: () => context.go(
                      '${Routes.recruiterJobs}/${job.id}',
                      extra: job,
                    ),
                  ),
                  const SizedBox(height: KpaSpacing.md),
                ],
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({
    required this.label,
    required this.value,
    required this.icon,
  });

  final String label;
  final String value;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(KpaSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, size: 20, color: theme.colorScheme.onSurfaceVariant),
            const SizedBox(height: KpaSpacing.sm),
            Text(value, style: theme.textTheme.headlineSmall),
            const SizedBox(height: KpaSpacing.xs),
            Text(
              label,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
