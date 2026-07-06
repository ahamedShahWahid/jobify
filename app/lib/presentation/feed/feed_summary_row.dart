import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/presentation/feed/feed_summary_controller.dart';
import 'package:jobify_app/presentation/preferences/preferences_controller.dart';
import 'package:jobify_app/presentation/resume/resume_controller.dart';
import 'package:jobify_app/presentation/routing/routes.dart';
import 'package:jobify_app/presentation/theme/jobify_colors.dart';
import 'package:jobify_app/presentation/theme/jobify_radii.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';
import 'package:jobify_app/presentation/theme/jobify_typography.dart';

/// Feed's home-summary row: Applications count / Saved count / match-profile
/// status. Replaces FeedNudgeBanner — the match-profile tile owns the same
/// résumé/preferences signal the banner used to, so there's one place that
/// decides "is your profile ready," not two.
class FeedSummaryRow extends ConsumerWidget {
  const FeedSummaryRow({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final summary = ref.watch(feedSummaryControllerProvider);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Expanded(
          child: _CountTile(
            icon: Icons.send_outlined,
            label: 'Applications',
            value: summary.whenOrNull(
              data: (s) => s.applicationsApprox
                  ? '${s.applicationsCount}+'
                  : '${s.applicationsCount}',
            ),
            isError: summary.hasError,
            onTap: () => context.go(Routes.applications),
            onRetry: () => ref.invalidate(feedSummaryControllerProvider),
          ),
        ),
        const SizedBox(width: JobifySpacing.sm),
        Expanded(
          child: _CountTile(
            icon: Icons.bookmark_outline,
            label: 'Saved',
            value: summary.whenOrNull(
              data: (s) =>
                  s.savedApprox ? '${s.savedCount}+' : '${s.savedCount}',
            ),
            isError: summary.hasError,
            onTap: () => context.go(Routes.saved),
            onRetry: () => ref.invalidate(feedSummaryControllerProvider),
          ),
        ),
        const SizedBox(width: JobifySpacing.sm),
        const Expanded(child: _MatchProfileTile()),
      ],
    );
  }
}

class _CountTile extends StatelessWidget {
  const _CountTile({
    required this.icon,
    required this.label,
    required this.value,
    required this.isError,
    required this.onTap,
    required this.onRetry,
  });

  final IconData icon;
  final String label;
  final String? value;
  final bool isError;
  final VoidCallback onTap;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return InkWell(
      onTap: isError ? onRetry : onTap,
      borderRadius: JobifyRadii.borderRadiusXl,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(JobifySpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 20, color: theme.colorScheme.onSurfaceVariant),
              const SizedBox(height: JobifySpacing.sm),
              if (isError)
                Icon(Icons.refresh, size: 18, color: theme.colorScheme.error)
              else
                Text(
                  value ?? '—',
                  style: JobifyTypography.mono(
                    fontSize: 20,
                    fontWeight: FontWeight.w600,
                    color: theme.colorScheme.onSurface,
                  ),
                ),
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
      ),
    );
  }
}

/// Watches the same two providers FeedNudgeBanner used to. Only decides from
/// resolved data — never renders off a loading or failed fetch (a bare
/// `.value == null` would flash the wrong state on every cold load).
class _MatchProfileTile extends ConsumerWidget {
  const _MatchProfileTile();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final resumeState = ref.watch(resumeControllerProvider);
    final prefsState = ref.watch(preferencesControllerProvider);
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final caveat = isDark ? JobifyColors.caveatDark : JobifyColors.caveatLight;
    final quiet = theme.colorScheme.onSurfaceVariant;

    if (!resumeState.hasValue || !prefsState.hasValue) {
      return _tile(
        context,
        icon: Icons.badge_outlined,
        label: 'Profile',
        color: quiet,
        onTap: () => context.go(Routes.profile),
      );
    }
    final resume = resumeState.value;
    if (resume == null) {
      return _tile(
        context,
        icon: Icons.upload_file_outlined,
        label: 'Upload résumé',
        color: caveat,
        onTap: () => context.push(Routes.resume),
      );
    }
    if (!prefsState.requireValue.isComplete) {
      return _tile(
        context,
        icon: Icons.badge_outlined,
        label: 'Finish your profile',
        color: caveat,
        onTap: () => context.push(Routes.preferences, extra: resume),
      );
    }
    return _tile(
      context,
      icon: Icons.check_circle_outline,
      label: 'Profile complete',
      color: quiet,
      onTap: () => context.go(Routes.profile),
    );
  }

  Widget _tile(
    BuildContext context, {
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) {
    final theme = Theme.of(context);
    return InkWell(
      onTap: onTap,
      borderRadius: JobifyRadii.borderRadiusXl,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(JobifySpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 20, color: color),
              const SizedBox(height: JobifySpacing.sm),
              Text(
                label,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: color,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
