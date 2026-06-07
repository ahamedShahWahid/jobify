import 'package:flutter/material.dart';

import 'package:kpa_app/data/jobs/recruiter_job_dto.dart';
import 'package:kpa_app/presentation/profile/ctc_format.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';

class RecruiterJobCard extends StatelessWidget {
  const RecruiterJobCard({
    required this.job,
    required this.onTap,
    super.key,
  });

  final RecruiterJobDto job;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isOpen = job.status == 'open';

    return Card(
      clipBehavior: Clip.hardEdge,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(KpaSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Title row + status chip
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Text(
                      job.title,
                      style: theme.textTheme.titleMedium,
                    ),
                  ),
                  const SizedBox(width: KpaSpacing.sm),
                  _StatusChip(isOpen: isOpen),
                ],
              ),
              const SizedBox(height: KpaSpacing.sm),

              // Exp band
              Text(
                '${job.minExpYears}–${job.maxExpYears} yrs exp',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),

              // CTC band (only when at least one bound is non-null)
              if (job.ctcMin != null || job.ctcMax != null) ...[
                const SizedBox(height: KpaSpacing.xs),
                Text(
                  '${formatCtcNum(job.ctcMin)} – ${formatCtcNum(job.ctcMax)}',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],

              const SizedBox(height: KpaSpacing.md),

              // Counts row
              Row(
                children: [
                  const Icon(Icons.people_outline, size: 16),
                  const SizedBox(width: KpaSpacing.xs),
                  Text(
                    '${job.applicantCount}',
                    style: theme.textTheme.labelMedium,
                  ),
                  const SizedBox(width: KpaSpacing.md),
                  const Icon(Icons.bolt_outlined, size: 16),
                  const SizedBox(width: KpaSpacing.xs),
                  Text(
                    '${job.surfacedMatchCount}',
                    style: theme.textTheme.labelMedium,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.isOpen});
  final bool isOpen;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final (label, bg, fg) = isOpen
        ? (
            'Open',
            theme.colorScheme.primaryContainer,
            theme.colorScheme.onPrimaryContainer,
          )
        : (
            'Closed',
            theme.colorScheme.surfaceContainerHighest,
            theme.colorScheme.onSurfaceVariant,
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
        style: theme.textTheme.labelSmall?.copyWith(color: fg),
      ),
    );
  }
}
