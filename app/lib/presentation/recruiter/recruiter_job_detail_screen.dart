import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:kpa_app/data/jobs/recruiter_job_dto.dart';
import 'package:kpa_app/presentation/profile/ctc_format.dart';
import 'package:kpa_app/presentation/recruiter/job_form_controller.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_jobs_controller.dart';
import 'package:kpa_app/presentation/routing/routes.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';
import 'package:kpa_app/presentation/widgets/kpa_empty_state.dart';
import 'package:kpa_app/presentation/widgets/kpa_loading_view.dart';

/// Recruiter-side job detail. When navigated from a card the full
/// [RecruiterJobDto] arrives via `GoRouterState.extra` (no refetch). On a
/// deep link (pasted URL) `initialJob` is null, so we resolve the job from the
/// include-closed jobs list by id.
class RecruiterJobDetailScreen extends ConsumerWidget {
  const RecruiterJobDetailScreen({
    required this.jobId,
    this.initialJob,
    super.key,
  });

  final String jobId;
  final RecruiterJobDto? initialJob;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final fromExtra = initialJob;
    if (fromExtra != null) {
      return _DetailScaffold(job: fromExtra);
    }

    // Deep-link path: find the job in the include-closed list.
    final value = ref.watch(recruiterJobsControllerProvider(true));
    return value.when(
      loading: () => const Scaffold(body: KpaLoadingView()),
      error: (_, __) => _NotFoundScaffold(),
      data: (state) {
        for (final j in state.items) {
          if (j.id == jobId) return _DetailScaffold(job: j);
        }
        return _NotFoundScaffold();
      },
    );
  }
}

class _NotFoundScaffold extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Job')),
      body: KpaEmptyState(
        headline: 'Job not found',
        body: 'It may have been deleted, or it belongs to another company.',
        icon: Icons.search_off_outlined,
        primaryAction: FilledButton(
          onPressed: () => context.go(Routes.recruiterJobs),
          child: const Text('Back to my jobs'),
        ),
      ),
    );
  }
}

class _DetailScaffold extends ConsumerWidget {
  const _DetailScaffold({required this.job});

  final RecruiterJobDto job;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final isOpen = job.status == 'open';
    final hasCtc = job.ctcMin != null || job.ctcMax != null;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Job'),
        actions: [
          TextButton(
            onPressed: () => context.go(
              '${Routes.recruiterJobs}/${job.id}/edit',
              extra: job,
            ),
            child: const Text('Edit'),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(KpaSpacing.lg),
        children: [
          Text(job.title, style: theme.textTheme.headlineSmall),
          const SizedBox(height: KpaSpacing.sm),
          Text(
            isOpen ? 'Open' : 'Closed',
            style: theme.textTheme.labelLarge?.copyWith(
              color: isOpen
                  ? theme.colorScheme.primary
                  : theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: KpaSpacing.lg),
          Wrap(
            spacing: KpaSpacing.xl,
            runSpacing: KpaSpacing.sm,
            children: [
              _Stat(
                icon: Icons.people_outline,
                label: 'Applicants',
                value: '${job.applicantCount}',
              ),
              _Stat(
                icon: Icons.bolt_outlined,
                label: 'Matches',
                value: '${job.surfacedMatchCount}',
              ),
            ],
          ),
          const SizedBox(height: KpaSpacing.lg),
          _Field(
            label: 'Experience',
            value: '${job.minExpYears}–${job.maxExpYears} yrs',
          ),
          if (hasCtc)
            _Field(
              label: 'CTC',
              value:
                  '${formatCtcNum(job.ctcMin)} – ${formatCtcNum(job.ctcMax)}',
            ),
          _Field(
            label: 'Locations',
            value: job.locations.isEmpty ? '—' : job.locations.join(', '),
          ),
          const SizedBox(height: KpaSpacing.lg),
          Text('Description', style: theme.textTheme.titleMedium),
          const SizedBox(height: KpaSpacing.sm),
          Text(job.description, style: theme.textTheme.bodyMedium),
          const SizedBox(height: KpaSpacing.xl),
          FilledButton.icon(
            onPressed: () => context.go(
              '${Routes.recruiterJobs}/${job.id}/applicants',
            ),
            icon: const Icon(Icons.people_outline),
            label: Text('View applicants (${job.applicantCount})'),
          ),
          const SizedBox(height: KpaSpacing.md),
          if (isOpen)
            OutlinedButton.icon(
              onPressed: () => _confirmClose(context, ref),
              icon: const Icon(Icons.lock_outline),
              label: const Text('Close this job'),
            ),
          const SizedBox(height: KpaSpacing.md),
          OutlinedButton.icon(
            onPressed: () => _confirmDelete(context, ref),
            icon: Icon(Icons.delete_outline, color: theme.colorScheme.error),
            label: Text(
              'Delete',
              style: TextStyle(color: theme.colorScheme.error),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _confirmClose(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('Close this job?'),
        content: const Text(
          "It won't appear in applicants' feeds. You can reopen it later by "
          'editing the job.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(c, true),
            child: const Text('Close job'),
          ),
        ],
      ),
    );
    if (!(ok ?? false)) return;
    await ref.read(jobFormControllerProvider.notifier).close(job.id);
    final state = ref.read(jobFormControllerProvider);
    if (state.hasError) {
      messenger.showSnackBar(
        const SnackBar(content: Text("Couldn't close the job. Try again.")),
      );
    }
  }

  Future<void> _confirmDelete(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('Delete this job?'),
        content: const Text('This cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(c, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (!(ok ?? false)) return;
    await ref.read(jobFormControllerProvider.notifier).delete(job.id);
    if (!context.mounted) return;
    final state = ref.read(jobFormControllerProvider);
    if (state.hasError) {
      messenger.showSnackBar(
        const SnackBar(content: Text("Couldn't delete the job. Try again.")),
      );
      return;
    }
    if (context.canPop()) {
      context.pop();
    } else {
      context.go(Routes.recruiterJobs);
    }
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.icon, required this.label, required this.value});
  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 18, color: theme.colorScheme.onSurfaceVariant),
        const SizedBox(width: KpaSpacing.xs),
        Text(value, style: theme.textTheme.titleMedium),
        const SizedBox(width: KpaSpacing.xs),
        Text(
          label,
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }
}

class _Field extends StatelessWidget {
  const _Field({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: KpaSpacing.xs),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 110,
            child: Text(
              label,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
          Expanded(child: Text(value, style: theme.textTheme.bodyMedium)),
        ],
      ),
    );
  }
}
