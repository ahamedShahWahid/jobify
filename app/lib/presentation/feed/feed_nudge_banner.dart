import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/presentation/preferences/preferences_controller.dart';
import 'package:jobify_app/presentation/resume/resume_controller.dart';
import 'package:jobify_app/presentation/routing/routes.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';

/// Derived, non-dismissible nudge shown above the feed. Fully computed from
/// resume + preferences state — no stored "dismissed" flag, so it simply
/// stops rendering once the underlying data is complete.
class FeedNudgeBanner extends ConsumerWidget {
  const FeedNudgeBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final resume = ref.watch(resumeControllerProvider).value;
    if (resume == null) {
      return _Banner(
        text: 'Upload your résumé so we can find you better roles.',
        actionLabel: 'Upload',
        onTap: () => context.push(Routes.resume),
      );
    }
    final prefs = ref.watch(preferencesControllerProvider).value;
    if (prefs != null && !prefs.isComplete) {
      return _Banner(
        text: "Tell us what you're looking for.",
        actionLabel: 'Answer',
        onTap: () => context.push(Routes.preferences, extra: resume),
      );
    }
    return const SizedBox.shrink();
  }
}

class _Banner extends StatelessWidget {
  const _Banner({
    required this.text,
    required this.actionLabel,
    required this.onTap,
  });

  final String text;
  final String actionLabel;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      margin: const EdgeInsets.only(bottom: JobifySpacing.md),
      color: theme.colorScheme.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(JobifySpacing.md),
        child: Row(
          children: [
            Expanded(
              child: Text(
                text,
                style: theme.textTheme.bodyMedium
                    ?.copyWith(color: theme.colorScheme.onPrimaryContainer),
              ),
            ),
            TextButton(onPressed: onTap, child: Text(actionLabel)),
          ],
        ),
      ),
    );
  }
}
