import 'package:flutter/material.dart';

import 'package:jobify_app/core/error/exceptions.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';

class JobifyErrorView extends StatelessWidget {
  const JobifyErrorView({
    super.key,
    this.error,
    this.headline,
    this.body,
    this.onRetry,
  });

  final Object? error;
  final String? headline;
  final String? body;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final (h, b) = _describe(error, headline, body);
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: JobifySpacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.error_outline,
              size: 48,
              color: theme.colorScheme.error,
            ),
            const SizedBox(height: JobifySpacing.lg),
            Text(
              h,
              style: theme.textTheme.titleMedium,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: JobifySpacing.sm),
            Text(
              b,
              style: theme.textTheme.bodyMedium,
              textAlign: TextAlign.center,
            ),
            if (onRetry != null) ...[
              const SizedBox(height: JobifySpacing.lg),
              FilledButton(
                onPressed: onRetry,
                child: const Text('Try again'),
              ),
            ],
          ],
        ),
      ),
    );
  }

  (String, String) _describe(
    Object? error,
    String? headline,
    String? body,
  ) {
    if (headline != null && body != null) return (headline, body);
    switch (error) {
      case NetworkException _:
        return (
          headline ?? "Couldn't reach Jobify",
          body ?? 'Check your connection and try again.',
        );
      case AuthException _:
        return (
          headline ?? 'Signed out',
          body ?? 'Your session ended. Sign in to continue.',
        );
      case ApiException(:final detail):
        return (
          headline ?? 'Something went wrong',
          body ?? (detail ?? 'Please try again in a moment.'),
        );
      default:
        return (
          headline ?? 'Something went wrong',
          body ?? 'An unexpected error occurred.',
        );
    }
  }
}
