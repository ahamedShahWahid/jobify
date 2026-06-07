// ignore_for_file: directives_ordering

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:kpa_app/data/auth/user_role.dart';
import 'package:kpa_app/presentation/auth/current_role_provider.dart';
import 'package:kpa_app/presentation/profile/ctc_format.dart';
import 'package:kpa_app/presentation/profile/me_controller.dart';
import 'package:kpa_app/presentation/profile/package_info_provider.dart';
import 'package:kpa_app/presentation/profile/sign_out_controller.dart';
import 'package:kpa_app/presentation/routing/routes.dart';
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
      appBar: AppBar(
        title: const Text('Profile'),
        actions: [
          TextButton(
            onPressed: () => context.go(Routes.profileEdit),
            child: const Text('Edit'),
          ),
        ],
      ),
      body: AsyncValueWidget(
        value: me,
        onRetry: () => ref.read(meControllerProvider.notifier).refresh(),
        data: (data) => ListView(
          padding: const EdgeInsets.all(KpaSpacing.lg),
          children: [
            Text(
              data.displayName ?? data.email,
              style: theme.textTheme.headlineSmall,
            ),
            const SizedBox(height: KpaSpacing.xs),
            Text(
              data.email,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            if (ref.watch(currentRoleProvider) == UserRole.applicant) ...[
              const SizedBox(height: KpaSpacing.xl),
              Card(
                child: ListTile(
                  leading: const Icon(Icons.business_center_outlined),
                  title: const Text("I'm hiring — post a job"),
                  subtitle:
                      const Text('Create your company to start recruiting'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => context.push(Routes.onboardingEmployer),
                ),
              ),
              const SizedBox(height: 12),
            ],
            if (data.applicant case final a?) ...[
              const SizedBox(height: KpaSpacing.xl),
              _DetailRow(
                label: 'Locations',
                value: a.locations.isEmpty ? '—' : a.locations.join(', '),
              ),
              if (formatYears(a.yearsExperience) case final years?)
                _DetailRow(label: 'Experience', value: years),
              if (a.noticePeriodDays != null)
                _DetailRow(
                  label: 'Notice period',
                  value: '${a.noticePeriodDays} days',
                ),
              _DetailRow(
                label: 'Current CTC',
                value: formatCtc(a.currentCtc),
              ),
              _DetailRow(
                label: 'Expected CTC',
                value: formatCtc(a.expectedCtc),
              ),
            ],
            const SizedBox(height: KpaSpacing.xl),
            Text('Account', style: theme.textTheme.titleMedium),
            const SizedBox(height: KpaSpacing.sm),
            ListTile(
              leading: const Icon(Icons.description_outlined),
              title: const Text('Résumé'),
              subtitle: const Text('Manage your résumé'),
              onTap: () => context.go(Routes.resume),
            ),
            ListTile(
              leading: const Icon(Icons.notifications_outlined),
              title: const Text('Notifications'),
              subtitle: const Text('View your notifications'),
              onTap: () => context.go(Routes.notifications),
            ),
            if (ref.watch(currentRoleProvider) == UserRole.applicant)
              ListTile(
                leading: const Icon(Icons.mail_outline),
                title: const Text('Pending invitations'),
                subtitle: const Text('Company invites to recruit'),
                onTap: () => context.go(Routes.profileInvites),
              ),
            ListTile(
              leading: const Icon(Icons.shield_outlined),
              title: const Text('Privacy & data'),
              subtitle: const Text('Preferences, export, delete'),
              onTap: () => context.go(Routes.privacy),
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

class _DetailRow extends StatelessWidget {
  const _DetailRow({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: KpaSpacing.xs),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 120,
            child: Text(
              label,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
          Expanded(child: Text(value, style: theme.textTheme.bodyMedium)),
        ],
      ),
    );
  }
}
