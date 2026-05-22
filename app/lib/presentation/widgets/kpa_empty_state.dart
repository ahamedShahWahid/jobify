import 'package:flutter/material.dart';

import 'package:kpa_app/presentation/theme/kpa_spacing.dart';

class KpaEmptyState extends StatelessWidget {
  const KpaEmptyState({
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
        padding: const EdgeInsets.symmetric(horizontal: KpaSpacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 48, color: theme.colorScheme.onSurfaceVariant),
            const SizedBox(height: KpaSpacing.lg),
            Text(
              headline,
              style: theme.textTheme.titleMedium,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: KpaSpacing.sm),
            Text(
              body,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
              textAlign: TextAlign.center,
            ),
            if (primaryAction != null) ...[
              const SizedBox(height: KpaSpacing.lg),
              primaryAction!,
            ],
          ],
        ),
      ),
    );
  }
}
