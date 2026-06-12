import 'package:flutter/material.dart';

import 'package:jobify_app/presentation/theme/jobify_spacing.dart';

class JobifyEmptyState extends StatelessWidget {
  const JobifyEmptyState({
    required this.headline,
    required this.body,
    super.key,
    this.icon = Icons.inbox_outlined,
    this.primaryAction,
  });

  final String headline;
  final String body;
  final IconData icon;
  final Widget? primaryAction;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: JobifySpacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 48, color: theme.colorScheme.onSurfaceVariant),
            const SizedBox(height: JobifySpacing.lg),
            Text(
              headline,
              style: theme.textTheme.titleMedium,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: JobifySpacing.sm),
            Text(
              body,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
              textAlign: TextAlign.center,
            ),
            if (primaryAction != null) ...[
              const SizedBox(height: JobifySpacing.lg),
              primaryAction!,
            ],
          ],
        ),
      ),
    );
  }
}
