import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:jobify_app/core/error/exceptions.dart';
import 'package:jobify_app/core/format/date_formats.dart';
import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/feed/match_feedback_rating.dart';
import 'package:jobify_app/data/feed/match_generator.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:jobify_app/presentation/applications/applications_screen.dart'
    show stageLabel;
import 'package:jobify_app/presentation/job_detail/action_bar.dart';
import 'package:jobify_app/presentation/job_detail/application_timeline_controller.dart';
import 'package:jobify_app/presentation/job_detail/apply_to_job_controller.dart';
import 'package:jobify_app/presentation/job_detail/job_detail_controller.dart';
import 'package:jobify_app/presentation/job_detail/match_feedback_controller.dart';
import 'package:jobify_app/presentation/job_detail/save_job_controller.dart';
import 'package:jobify_app/presentation/job_detail/unsave_job_controller.dart';
import 'package:jobify_app/presentation/theme/jobify_colors.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';
import 'package:jobify_app/presentation/theme/jobify_typography.dart';
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
                    if (d.application != null) ...[
                      const SizedBox(height: JobifySpacing.lg),
                      _ApplicationTimeline(
                        applicationId: d.application!.id,
                      ),
                    ],
                    if (d.match != null) ...[
                      const SizedBox(height: JobifySpacing.lg),
                      _MatchCard(match: d.match!),
                      _MatchFeedbackRow(
                        jobId: d.job.id,
                        current: d.match!.myFeedback,
                      ),
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

class _CaveatLine extends StatelessWidget {
  const _CaveatLine({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final amber = isDark ? JobifyColors.caveatDark : JobifyColors.caveatLight;
    return Container(
      padding: const EdgeInsets.only(left: JobifySpacing.sm),
      decoration: BoxDecoration(
        border: Border(left: BorderSide(color: amber, width: 2.5)),
      ),
      child: Text(
        'Counts against: $text',
        style: Theme.of(context).textTheme.bodySmall?.copyWith(color: amber),
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
              Text(
                exp.fit,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontSize: 17,
                  fontWeight: FontWeight.w500,
                  height: 1.4,
                  color: theme.colorScheme.onSurface,
                ),
              ),
              if (exp.caveat != null) ...[
                const SizedBox(height: JobifySpacing.sm),
                _CaveatLine(text: exp.caveat!),
              ],
              const SizedBox(height: JobifySpacing.sm),
              Text(
                exp.generator.label,
                style: JobifyTypography.mono(
                  fontSize: 11,
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _MatchFeedbackRow extends ConsumerWidget {
  const _MatchFeedbackRow({required this.jobId, required this.current});

  final String jobId;
  final MatchFeedbackRating? current;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final pending = ref.watch(matchFeedbackControllerProvider(jobId)).isLoading;
    final notifier = ref.read(matchFeedbackControllerProvider(jobId).notifier);

    void toggle(MatchFeedbackRating rating) {
      if (pending) return;
      if (current == rating) {
        notifier.clear(); // tapping the active thumb clears the rating
      } else {
        notifier.rate(rating);
      }
    }

    return Padding(
      padding: const EdgeInsets.only(top: JobifySpacing.md),
      child: Row(
        children: [
          Expanded(
            child: Text(
              'Was this match right for you?',
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
          ),
          IconButton(
            tooltip: 'Good match',
            visualDensity: VisualDensity.compact,
            icon: Icon(
              current == MatchFeedbackRating.up
                  ? Icons.thumb_up
                  : Icons.thumb_up_outlined,
              size: 20,
            ),
            onPressed: pending ? null : () => toggle(MatchFeedbackRating.up),
          ),
          IconButton(
            tooltip: 'Not interested',
            visualDensity: VisualDensity.compact,
            icon: Icon(
              current == MatchFeedbackRating.down
                  ? Icons.thumb_down
                  : Icons.thumb_down_outlined,
              size: 20,
            ),
            onPressed: pending ? null : () => toggle(MatchFeedbackRating.down),
          ),
        ],
      ),
    );
  }
}

/// Compact stage-change history for one application. Degrades to nothing
/// (leaving the stage chip elsewhere as the sole status signal) while
/// loading, on error, or when there are no events yet — spec rule.
class _ApplicationTimeline extends ConsumerWidget {
  const _ApplicationTimeline({required this.applicationId});
  final String applicationId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final events = ref.watch(applicationTimelineProvider(applicationId));
    return events.maybeWhen(
      data: (items) {
        if (items.isEmpty) return const SizedBox.shrink();
        final theme = Theme.of(context);
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Timeline', style: theme.textTheme.titleMedium),
            const SizedBox(height: JobifySpacing.sm),
            for (final e in items)
              Padding(
                padding: const EdgeInsets.only(bottom: JobifySpacing.xs),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        stageLabel(e.toStage),
                        style: theme.textTheme.bodyMedium,
                      ),
                    ),
                    Text(
                      jobifyShortDateFormat.format(e.createdAt),
                      style: JobifyTypography.mono(
                        fontSize: 12,
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        );
      },
      orElse: () => const SizedBox.shrink(),
    );
  }
}
