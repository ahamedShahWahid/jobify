// ignore_for_file: directives_ordering

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/presentation/privacy/delete_account_controller.dart';
import 'package:jobify_app/presentation/routing/routes.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';

class DeleteAccountScreen extends ConsumerStatefulWidget {
  const DeleteAccountScreen({super.key});

  @override
  ConsumerState<DeleteAccountScreen> createState() =>
      _DeleteAccountScreenState();
}

class _DeleteAccountScreenState extends ConsumerState<DeleteAccountScreen> {
  final _confirmationController = TextEditingController();

  static const _requiredPhrase = 'DELETE_MY_ACCOUNT';

  @override
  void dispose() {
    _confirmationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final controllerState = ref.watch(deleteAccountControllerProvider);

    // Listen for submission errors and show a snackbar.
    ref.listen<AsyncValue<void>>(deleteAccountControllerProvider, (_, next) {
      next.whenOrNull(
        error: (e, _) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text("Couldn't delete your account. Try again."),
            ),
          );
        },
      );
    });

    final theme = Theme.of(context);
    final isLoading = controllerState.isLoading;

    return Scaffold(
      appBar: AppBar(title: const Text('Delete my account')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(JobifySpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Warning banner.
            Container(
              padding: const EdgeInsets.all(JobifySpacing.md),
              decoration: BoxDecoration(
                color: theme.colorScheme.errorContainer,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    Icons.warning_amber_outlined,
                    color: theme.colorScheme.onErrorContainer,
                  ),
                  const SizedBox(width: JobifySpacing.sm),
                  Expanded(
                    child: Text(
                      'This will permanently delete your personal data '
                      'on Jobify. This action is irreversible.',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: theme.colorScheme.onErrorContainer,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: JobifySpacing.xl),
            Text('What will happen:', style: theme.textTheme.titleSmall),
            const SizedBox(height: JobifySpacing.sm),
            ..._bullets(theme),

            const SizedBox(height: JobifySpacing.xl),
            OutlinedButton.icon(
              icon: const Icon(Icons.download_outlined),
              label: const Text('Download my data'),
              onPressed: () => context.go(Routes.privacy),
            ),
            const SizedBox(height: JobifySpacing.xs),
            Text(
              'Before you continue, we recommend downloading your data.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),

            const SizedBox(height: JobifySpacing.xl),
            Text(
              'To confirm, type $_requiredPhrase below:',
              style: theme.textTheme.bodyMedium,
            ),
            const SizedBox(height: JobifySpacing.sm),
            TextField(
              controller: _confirmationController,
              enabled: !isLoading,
              autocorrect: false,
              textCapitalization: TextCapitalization.characters,
              decoration: const InputDecoration(
                border: OutlineInputBorder(),
                hintText: _requiredPhrase,
              ),
            ),

            const SizedBox(height: JobifySpacing.xl),

            // The submit button — enabled only when the text matches exactly.
            ValueListenableBuilder<TextEditingValue>(
              valueListenable: _confirmationController,
              builder: (_, value, __) {
                final enabled = value.text == _requiredPhrase && !isLoading;
                return FilledButton(
                  style: FilledButton.styleFrom(
                    backgroundColor: theme.colorScheme.error,
                    foregroundColor: theme.colorScheme.onError,
                  ),
                  onPressed: enabled ? () => _attemptDelete(context) : null,
                  child: isLoading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Text('Delete my account'),
                );
              },
            ),
            const SizedBox(height: JobifySpacing.md),
            OutlinedButton(
              onPressed: isLoading ? null : () => context.pop(),
              child: const Text('Cancel'),
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _bullets(ThemeData theme) {
    const items = [
      'Your profile, resume, applications, and saved jobs are removed.',
      'Your match history and notifications are erased.',
      'Anonymized employer-side analytics survive (apply counts only).',
    ];
    return items
        .map(
          (text) => Padding(
            padding: const EdgeInsets.only(bottom: JobifySpacing.xs),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('• '),
                Expanded(
                  child: Text(text, style: theme.textTheme.bodyMedium),
                ),
              ],
            ),
          ),
        )
        .toList();
  }

  Future<void> _attemptDelete(BuildContext context) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('Are you absolutely sure?'),
        content: const Text(
          'Your account and all associated data will be permanently deleted.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(c).colorScheme.error,
              foregroundColor: Theme.of(c).colorScheme.onError,
            ),
            onPressed: () => Navigator.pop(c, true),
            child: const Text('Yes, delete'),
          ),
        ],
      ),
    );
    if (!(ok ?? false)) return;
    await ref.read(deleteAccountControllerProvider.notifier).submit();
  }
}
