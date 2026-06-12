import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:jobify_app/core/error/exceptions.dart';
import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/feed/match_generator.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:jobify_app/presentation/job_detail/action_bar.dart';
import 'package:jobify_app/presentation/job_detail/apply_to_job_controller.dart';
import 'package:jobify_app/presentation/job_detail/job_detail_controller.dart';
import 'package:jobify_app/presentation/job_detail/save_job_controller.dart';
import 'package:jobify_app/presentation/job_detail/unsave_job_controller.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';
import 'package:jobify_app/presentation/widgets/async_value_widget.dart';
import 'package:jobify_app/presentation/widgets/jobify_empty_state.dart';
import 'package:jobify_app/presentation/widgets/jobify_score_badge.dart';

class JobDetailScreen extends ConsumerWidget {
  const JobDetailScreen({required this.jobId, super.key});
  final String jobId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    void listenErr(AsyncValue<dynamic> v) {
      v.whenOrNull(
        error: (e, _) {
          final msg = e is ApiException
              ? (e.detail ?? 'Action failed')
              : "Couldn't reach Jobify.";
          ScaffoldMessenger.of(context)
              .showSnackBar(SnackBar(content: Text(msg)));
        },
      );
    }

    ref
      ..listen<AsyncValue<dynamic>>(
        applyToJobControllerProvider(jobId),
        (_, n) => listenErr(n),
      )
      ..listen<AsyncValue<dynamic>>(
        saveJobControllerProvider(jobId),
        (_, n) => listenErr(n),
      )
      ..listen<AsyncValue<dynamic>>(
        unsaveJobControllerProvider(jobId),
        (_, n) => listenErr(n),
      );

    final value = ref.watch(jobDetailControllerProvider(jobId));
    return Scaffold(
      appBar: AppBar(leading: BackButton(onPressed: () => context.pop())),
      body: AsyncValueWidget<JobDetailDto>(
        value: value,
        onRetry: () =>
            ref.read(jobDetailControllerProvider(jobId).notifier).refresh(),
        error: (e, s) {
          if (e is ApiException && e.statusCode == 404) {
            return JobifyEmptyState(
              headline: 'This job is no longer available',
              body: 'It may have been closed or removed.',
              primaryAction: FilledButton(
                onPressed: () => context.pop(),
                child: const Text('Back'),
              ),
            );
          }
          return Center(child: Text(e.toString()));
        },
        data: (d) => Column(
          children: [
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(JobifySpacing.lg),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      d.employer.name,
                      style: Theme.of(context).textTheme.labelLarge,
                    ),
                    const SizedBox(height: JobifySpacing.xs),
                    Text(
                      d.job.title,
                      style: Theme.of(context).textTheme.headlineMedium,
                    ),
                    const SizedBox(height: JobifySpacing.xs),
                    Text(
                      d.job.locations.join(', '),
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                    if (d.match != null) ...[
                      const SizedBox(height: JobifySpacing.lg),
                      _MatchCard(match: d.match!),
                    ],
                    if (d.job.description != null) ...[
                      const SizedBox(height: JobifySpacing.xl),
                      Text(
                        d.job.description!,
                        style: Theme.of(context).textTheme.bodyLarge,
                      ),
                    ],
                  ],
                ),
              ),
            ),
            ActionBar(detail: d),
          ],
        ),
      ),
    );
  }
}

class _MatchCard extends StatelessWidget {
  const _MatchCard({required this.match});
  final MatchSummaryDto match;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final exp = match.explanation;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(JobifySpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(
                  'Why this match',
                  style: theme.textTheme.titleMedium,
                ),
                const Spacer(),
                JobifyScoreBadge(score: match.totalScore),
              ],
            ),
            if (exp != null) ...[
              const SizedBox(height: JobifySpacing.md),
              Text(exp.fit, style: theme.textTheme.bodyMedium),
              if (exp.caveat != null) ...[
                const SizedBox(height: JobifySpacing.sm),
                Text(
                  exp.caveat!,
                  style: theme.textTheme.bodySmall,
                ),
              ],
              const SizedBox(height: JobifySpacing.sm),
              Text(exp.generator.label, style: theme.textTheme.labelSmall),
            ],
          ],
        ),
      ),
    );
  }
}
