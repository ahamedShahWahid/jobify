// ignore_for_file: directives_ordering

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/core/consent/consent_scope.dart';
import 'package:jobify_app/presentation/privacy/privacy_controller.dart';
import 'package:jobify_app/presentation/privacy/privacy_state.dart';
import 'package:jobify_app/presentation/routing/routes.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';
import 'package:jobify_app/presentation/widgets/async_value_widget.dart';

class PrivacyScreen extends ConsumerWidget {
  const PrivacyScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(privacyControllerProvider);

    // Show rollback snackbar whenever mutationError is set.
    ref.listen<AsyncValue<PrivacyState>>(privacyControllerProvider, (_, next) {
      final err = next.value?.mutationError;
      if (err != null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text("Couldn't update preference. Change was reverted."),
          ),
        );
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('Privacy & data')),
      body: AsyncValueWidget(
        value: state,
        onRetry: () => ref.invalidate(privacyControllerProvider),
        data: (data) => _PrivacyBody(data: data),
      ),
    );
  }
}

class _PrivacyBody extends ConsumerWidget {
  const _PrivacyBody({required this.data});

  final PrivacyState data;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);

    // Build a lookup map from scope wire string → granted bool.
    final consentMap = {
      for (final c in data.consents) c.scope: c.granted,
    };

    return Stack(
      children: [
        ListView(
          padding: const EdgeInsets.all(JobifySpacing.lg),
          children: [
            // ── Notification preferences section ──────────────────────────
            Text(
              'Notification preferences',
              style: theme.textTheme.titleMedium,
            ),
            const SizedBox(height: JobifySpacing.sm),
            ...ConsentScope.v0VisibleScopes.map((scope) {
              final granted = consentMap[scope.wire] ?? false;
              final labels = _consentLabel(scope);
              return SwitchListTile.adaptive(
                key: Key('toggle-${scope.wire}'),
                title: Text(labels.$1),
                subtitle: Text(labels.$2),
                value: granted,
                onChanged: (val) => _onToggle(context, ref, scope, val),
                contentPadding: EdgeInsets.zero,
              );
            }),

            const SizedBox(height: JobifySpacing.xl),
            const Divider(),
            const SizedBox(height: JobifySpacing.xl),

            // ── Your data section ─────────────────────────────────────────
            Text('Your data', style: theme.textTheme.titleMedium),
            const SizedBox(height: JobifySpacing.sm),
            Text(
              'A copy of everything we know about you (JSON).',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: JobifySpacing.md),
            OutlinedButton.icon(
              icon: const Icon(Icons.download_outlined),
              label: const Text('Download my data'),
              onPressed: data.exportInProgress
                  ? null
                  : () => _exportData(context, ref),
            ),

            const SizedBox(height: JobifySpacing.xl),
            const Divider(),
            const SizedBox(height: JobifySpacing.xl),

            // ── Account section ───────────────────────────────────────────
            Text('Account', style: theme.textTheme.titleMedium),
            const SizedBox(height: JobifySpacing.sm),
            Text(
              "Permanently erase your data. This can't be undone.",
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: JobifySpacing.md),
            FilledButton(
              style: FilledButton.styleFrom(
                backgroundColor: theme.colorScheme.error,
                foregroundColor: theme.colorScheme.onError,
              ),
              onPressed: () => context.go(Routes.privacyDelete),
              child: const Text('Delete my account'),
            ),
          ],
        ),

        // Export-in-progress overlay.
        if (data.exportInProgress)
          const ModalBarrier(dismissible: false, color: Colors.black26),
        if (data.exportInProgress)
          const Center(child: CircularProgressIndicator.adaptive()),
      ],
    );
  }

  Future<void> _onToggle(
    BuildContext context,
    WidgetRef ref,
    ConsentScope scope,
    bool val,
  ) async {
    // email_transactional OFF requires confirmation first.
    if (scope == ConsentScope.emailTransactional && !val) {
      final ok = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: const Text('Turn off service emails?'),
          content: const Text(
            "You won't receive emails about your applications, "
            'matches, or account. Are you sure?',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(c, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(c, true),
              child: const Text('Turn off'),
            ),
          ],
        ),
      );
      if (!(ok ?? false)) return;
    }

    await ref
        .read(privacyControllerProvider.notifier)
        .setConsent(scope.wire, granted: val);
  }

  Future<void> _exportData(BuildContext context, WidgetRef ref) async {
    final result =
        await ref.read(privacyControllerProvider.notifier).exportData();
    if (!context.mounted) return;
    if (result != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Your data is on your clipboard.\n'
            'Paste it into a text editor and save as a .json file.',
          ),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Couldn't export your data. Try again.")),
      );
    }
  }
}

/// Returns (title, subtitle) for a consent scope.
({String title, String subtitle}) _consentLabelRecord(ConsentScope scope) {
  return switch (scope) {
    ConsentScope.emailTransactional => (
        title: 'Service updates',
        subtitle: 'Email about your applications, matches, and account.',
      ),
    ConsentScope.emailMarketing => (
        title: 'Job recommendations',
        subtitle: 'Weekly digest of jobs that fit your profile.',
      ),
    ConsentScope.inAppNotifications => (
        title: 'In-app notifications',
        subtitle: 'See alerts inside the app.',
      ),
    _ => (title: scope.wire, subtitle: ''),
  };
}

(String, String) _consentLabel(ConsentScope scope) {
  final r = _consentLabelRecord(scope);
  return (r.title, r.subtitle);
}
