import 'package:flutter/material.dart';

import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/jobs/job_status.dart';
import 'package:jobify_app/presentation/theme/jobify_colors.dart';
import 'package:jobify_app/presentation/theme/jobify_radii.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';
import 'package:jobify_app/presentation/theme/jobify_typography.dart';
import 'package:jobify_app/presentation/widgets/jobify_score_badge.dart';

class FeedItemCard extends StatelessWidget {
  const FeedItemCard({
    required this.job,
    required this.employer,
    required this.onTap,
    this.match,
    this.explanation,
    this.showScore = true,
    super.key,
  });

  final JobSummaryDto job;
  final EmployerSummaryDto employer;
  final MatchSummaryDto? match;
  final ExplanationDto? explanation;
  final VoidCallback onTap;
  final bool showScore;

  String _ago(DateTime d) {
    final delta = DateTime.now().toUtc().difference(d.toUtc());
    if (delta.inDays >= 30) return '${(delta.inDays / 30).floor()}mo ago';
    if (delta.inDays >= 1) return '${delta.inDays}d ago';
    if (delta.inHours >= 1) return '${delta.inHours}h ago';
    return 'just now';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isClosed = job.status != JobStatus.open;
    final meta = [
      if (job.locations.isNotEmpty) job.locations.join(', '),
      _ago(job.postedAt),
    ].join(' · ');
    return Card(
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(JobifySpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      employer.name.toUpperCase(),
                      style: theme.textTheme.labelMedium?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                        letterSpacing: 0.4,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  const SizedBox(width: JobifySpacing.sm),
                  if (isClosed)
                    const _ClosedPill()
                  else if (showScore && match != null)
                    JobifyScoreBadge(score: match!.totalScore),
                ],
              ),
              const SizedBox(height: JobifySpacing.xs),
              Text(job.title, style: theme.textTheme.titleMedium),
              if (explanation != null) ...[
                const SizedBox(height: JobifySpacing.sm),
                Text(
                  explanation!.fit,
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontSize: 18.5,
                    fontWeight: FontWeight.w600,
                    height: 1.35,
                    letterSpacing: -0.3,
                    color: theme.colorScheme.onSurface,
                  ),
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                ),
                if (explanation!.caveat != null) ...[
                  const SizedBox(height: JobifySpacing.sm),
                  _CaveatLine(text: explanation!.caveat!),
                ],
              ],
              const SizedBox(height: JobifySpacing.md),
              Text(
                meta,
                style: JobifyTypography.mono(
                  fontSize: 12,
                  fontWeight: FontWeight.w400,
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
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
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
      ),
    );
  }
}

class _ClosedPill extends StatelessWidget {
  const _ClosedPill();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: JobifySpacing.sm,
        vertical: JobifySpacing.xs,
      ),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest,
        border: Border.all(color: theme.colorScheme.outlineVariant),
        borderRadius: JobifyRadii.borderRadiusPill,
      ),
      child: Text(
        'Closed',
        style: theme.textTheme.labelSmall
            ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
      ),
    );
  }
}
