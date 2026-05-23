// ignore_for_file: directives_ordering

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:kpa_app/presentation/profile/me_controller.dart';
import 'package:kpa_app/presentation/profile/package_info_provider.dart';
import 'package:kpa_app/presentation/profile/sign_out_controller.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';
import 'package:kpa_app/presentation/widgets/async_value_widget.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

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
          padding: const EdgeInsets.all(KpaSpacing.lg),
          children: [
            Text(
              data.user.displayName ?? data.user.email,
              style: theme.textTheme.headlineSmall,
            ),
            const SizedBox(height: KpaSpacing.xs),
            Text(
              data.user.email,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: KpaSpacing.xl),
            Text('Account', style: theme.textTheme.titleMedium),
            const SizedBox(height: KpaSpacing.sm),
            const ListTile(
              leading: Icon(Icons.description_outlined),
              title: Text('Resume'),
              subtitle: Text('Coming soon'),
              enabled: false,
            ),
            const ListTile(
              leading: Icon(Icons.notifications_outlined),
              title: Text('Notifications'),
              subtitle: Text('Coming soon'),
              enabled: false,
            ),
            const SizedBox(height: KpaSpacing.xxl),
            OutlinedButton(
              onPressed: signOut.isLoading
                  ? null
                  : () => _confirmSignOut(context, ref),
              child: Text(signOut.isLoading ? 'Signing out…' : 'Sign out'),
            ),
            const SizedBox(height: KpaSpacing.xxl),
            ref.watch(packageInfoProvider).when(
              data: (info) => Center(
                child: Text(
                  'v${info.version} (${info.buildNumber})',
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
              loading: () => const SizedBox.shrink(),
              error: (_, __) => const SizedBox.shrink(),
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
        content: const Text(
          "You'll need to sign in again to continue.",
        ),
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
