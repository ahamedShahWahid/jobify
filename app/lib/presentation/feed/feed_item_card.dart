import 'package:flutter/material.dart';

import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/jobs/job_status.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';
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
                      employer.name,
                      style: theme.textTheme.labelLarge,
                    ),
                  ),
                  if (isClosed)
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: JobifySpacing.sm,
                        vertical: JobifySpacing.xs,
                      ),
                      decoration: BoxDecoration(
                        color: theme.colorScheme.outlineVariant,
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text(
                        'Closed',
                        style: theme.textTheme.labelSmall,
                      ),
                    )
                  else if (showScore && match != null)
                    JobifyScoreBadge(score: match!.totalScore),
                ],
              ),
              const SizedBox(height: JobifySpacing.sm),
              Text(job.title, style: theme.textTheme.titleMedium),
              const SizedBox(height: JobifySpacing.xs),
              Text(
                meta,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              if (explanation != null) ...[
                const SizedBox(height: JobifySpacing.md),
                Text(
                  explanation!.fit,
                  style: theme.textTheme.bodyMedium,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                if (explanation!.caveat != null) ...[
                  const SizedBox(height: JobifySpacing.xs),
                  Text(
                    explanation!.caveat!,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ],
            ],
          ),
        ),
      ),
    );
  }
}
