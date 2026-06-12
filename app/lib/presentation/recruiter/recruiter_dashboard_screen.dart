import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/presentation/recruiter/recruiter_dashboard_controller.dart';
import 'package:jobify_app/presentation/recruiter/recruiter_job_card.dart';
import 'package:jobify_app/presentation/routing/routes.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';
import 'package:jobify_app/presentation/widgets/async_value_widget.dart';
import 'package:jobify_app/presentation/widgets/jobify_empty_state.dart';

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
            padding: const EdgeInsets.all(JobifySpacing.lg),
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
                  const SizedBox(width: JobifySpacing.md),
                  Expanded(
                    child: _SummaryCard(
                      label: 'Applicants',
                      value: '${summary.totalApplicants}',
                      icon: Icons.people_outline,
                    ),
                  ),
                  const SizedBox(width: JobifySpacing.md),
                  Expanded(
                    child: _SummaryCard(
                      label: 'Matches',
                      value: '${summary.totalSurfacedMatches}',
                      icon: Icons.bolt_outlined,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: JobifySpacing.xl),
              if (summary.recentJobs.isEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: JobifySpacing.xxl),
                  child: JobifyEmptyState(
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
                const SizedBox(height: JobifySpacing.sm),
                for (final job in summary.recentJobs) ...[
                  RecruiterJobCard(
                    job: job,
                    onTap: () => context.go(
                      '${Routes.recruiterJobs}/${job.id}',
                      extra: job,
                    ),
                  ),
                  const SizedBox(height: JobifySpacing.md),
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
        padding: const EdgeInsets.all(JobifySpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, size: 20, color: theme.colorScheme.onSurfaceVariant),
            const SizedBox(height: JobifySpacing.sm),
            Text(value, style: theme.textTheme.headlineSmall),
            const SizedBox(height: JobifySpacing.xs),
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
