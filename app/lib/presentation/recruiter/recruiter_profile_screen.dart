import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/presentation/profile/me_controller.dart';
import 'package:jobify_app/presentation/profile/sign_out_controller.dart';
import 'package:jobify_app/presentation/routing/routes.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';
import 'package:jobify_app/presentation/widgets/async_value_widget.dart';

class RecruiterProfileScreen extends ConsumerWidget {
  const RecruiterProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final me = ref.watch(meControllerProvider);
    final signOut = ref.watch(signOutControllerProvider);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: AsyncValueWidget(
        value: me,
        onRetry: () => ref.read(meControllerProvider.notifier).refresh(),
        data: (data) => ListView(
          padding: const EdgeInsets.all(JobifySpacing.lg),
          children: [
            Text(
              data.displayName ?? data.email ?? 'Profile',
              style: theme.textTheme.headlineSmall,
            ),
            const SizedBox(height: JobifySpacing.xs),
            if (data.email case final email?)
              Text(
                email,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            const SizedBox(height: JobifySpacing.xl),
            ListTile(
              leading: const Icon(Icons.shield_outlined),
              title: const Text('Privacy & data'),
              subtitle: const Text('Preferences, export, delete'),
              onTap: () => context.go(Routes.privacy),
            ),
            const SizedBox(height: JobifySpacing.xxl),
            OutlinedButton(
              onPressed: signOut.isLoading
                  ? null
                  : () => _confirmSignOut(context, ref),
              child: Text(signOut.isLoading ? 'Signing out…' : 'Sign out'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _confirmSignOut(BuildContext ctx, WidgetRef ref) async {
    final ok = await showDialog<bool>(
      context: ctx,
      builder: (c) => AlertDialog(
        title: const Text('Sign out?'),
        content: const Text("You'll need to sign in again to continue."),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(c, true),
            child: const Text('Sign out'),
          ),
        ],
      ),
    );
    if (ok ?? false) {
      await ref.read(signOutControllerProvider.notifier).submit();
    }
  }
}
