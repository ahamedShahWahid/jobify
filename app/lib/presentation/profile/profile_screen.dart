// ignore_for_file: directives_ordering

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/data/auth/user_role.dart';
import 'package:jobify_app/data/me/me_dto.dart';
import 'package:jobify_app/data/preferences/desired_role.dart';
import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/presentation/auth/current_role_provider.dart';
import 'package:jobify_app/presentation/preferences/preferences_controller.dart';
import 'package:jobify_app/presentation/profile/ctc_format.dart';
import 'package:jobify_app/presentation/profile/me_controller.dart';
import 'package:jobify_app/presentation/profile/package_info_provider.dart';
import 'package:jobify_app/presentation/profile/sign_out_controller.dart';
import 'package:jobify_app/presentation/routing/routes.dart';
import 'package:jobify_app/presentation/theme/jobify_colors.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';
import 'package:jobify_app/presentation/theme/jobify_typography.dart';
import 'package:jobify_app/presentation/theme/theme_mode_controller.dart';
import 'package:jobify_app/presentation/widgets/arrive.dart';
import 'package:jobify_app/presentation/widgets/async_value_widget.dart';
import 'package:jobify_app/presentation/widgets/bold_header.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final me = ref.watch(meControllerProvider);
    final preferences = ref.watch(preferencesControllerProvider);
    final signOut = ref.watch(signOutControllerProvider);
    final theme = Theme.of(context);
    final isApplicant = ref.watch(currentRoleProvider) == UserRole.applicant;

    return BoldScaffold(
      header: BoldHeader(
        title: 'Profile',
        trailing: TextButton(
          onPressed: () => context.go(Routes.profileEdit),
          child: const Text('Edit'),
        ),
      ),
      child: AsyncValueWidget(
        value: me,
        onRetry: () => ref.read(meControllerProvider.notifier).refresh(),
        data: (data) {
          var arriveIndex = 0;
          Widget arrive(Widget child) =>
              Arrive(index: arriveIndex++, child: child);

          final rows = data.applicant != null
              ? _matchProfileRows(
                  a: data.applicant!,
                  preferences: preferences,
                  onRetry: () => ref.invalidate(preferencesControllerProvider),
                  onAdd: () => context.go(Routes.profileEdit),
                )
              : const <Widget>[];

          return ListView(
            padding: const EdgeInsets.all(JobifySpacing.lg),
            children: [
              arrive(
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
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
                  ],
                ),
              ),
              if (isApplicant) ...[
                const SizedBox(height: JobifySpacing.xl),
                arrive(
                  Card(
                    child: ListTile(
                      leading: const Icon(Icons.business_center_outlined),
                      title: const Text("I'm hiring — post a job"),
                      subtitle: const Text(
                        'Create your company to start recruiting',
                      ),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => context.push(Routes.onboardingEmployer),
                    ),
                  ),
                ),
              ],
              if (rows.isNotEmpty) ...[
                const SizedBox(height: JobifySpacing.xl),
                arrive(
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Match profile', style: theme.textTheme.titleMedium),
                      const SizedBox(height: JobifySpacing.sm),
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.symmetric(
                            horizontal: JobifySpacing.lg,
                            vertical: JobifySpacing.xs,
                          ),
                          child: Column(
                            children: [
                              for (var i = 0; i < rows.length; i++) ...[
                                if (i > 0)
                                  Divider(
                                    height: 1,
                                    color: theme.colorScheme.outlineVariant,
                                  ),
                                rows[i],
                              ],
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
              const SizedBox(height: JobifySpacing.xl),
              arrive(
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Account', style: theme.textTheme.titleMedium),
                    const SizedBox(height: JobifySpacing.sm),
                    Card(
                      clipBehavior: Clip.antiAlias,
                      child: Column(
                        children: [
                          ListTile(
                            leading: const Icon(Icons.description_outlined),
                            title: const Text('Résumé'),
                            subtitle: const Text('Manage your résumé'),
                            onTap: () => context.go(Routes.resume),
                          ),
                          Divider(
                            height: 1,
                            color: theme.colorScheme.outlineVariant,
                          ),
                          ListTile(
                            leading: const Icon(Icons.notifications_outlined),
                            title: const Text('Notifications'),
                            subtitle: const Text('View your notifications'),
                            onTap: () => context.go(Routes.notifications),
                          ),
                          if (isApplicant) ...[
                            Divider(
                              height: 1,
                              color: theme.colorScheme.outlineVariant,
                            ),
                            ListTile(
                              leading: const Icon(Icons.mail_outline),
                              title: const Text('Pending invitations'),
                              subtitle:
                                  const Text('Company invites to recruit'),
                              onTap: () => context.go(Routes.profileInvites),
                            ),
                          ],
                          Divider(
                            height: 1,
                            color: theme.colorScheme.outlineVariant,
                          ),
                          ListTile(
                            leading: const Icon(Icons.shield_outlined),
                            title: const Text('Privacy & data'),
                            subtitle: const Text('Preferences, export, delete'),
                            onTap: () => context.go(Routes.privacy),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: JobifySpacing.xl),
              arrive(
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Appearance', style: theme.textTheme.titleMedium),
                    const SizedBox(height: JobifySpacing.sm),
                    _AppearanceSelector(),
                  ],
                ),
              ),
              const SizedBox(height: JobifySpacing.xxl),
              arrive(
                OutlinedButton(
                  onPressed: signOut.isLoading
                      ? null
                      : () => _confirmSignOut(context, ref),
                  child: Text(signOut.isLoading ? 'Signing out…' : 'Sign out'),
                ),
              ),
              const SizedBox(height: JobifySpacing.xxl),
              ref.watch(packageInfoProvider).when(
                    data: (info) => Center(
                      child: Text(
                        'v${info.version} (${info.buildNumber})',
                        style: JobifyTypography.mono(
                          fontSize: 11,
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ),
                    loading: () => const SizedBox.shrink(),
                    error: (_, __) => const SizedBox.shrink(),
                  ),
            ],
          );
        },
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

/// Builds the "Match profile" spec-sheet rows — the literal data the
/// matching algorithm reads about this applicant. Desired role, locations,
/// and expected CTC are the three fields [PreferencesDto.isComplete] tracks;
/// when one is missing, its row becomes a tappable "Add" prompt (caveat
/// amber — the app's existing "honest weakness" token) instead of a dead
/// dash, since a missing field here concretely means weaker matches.
List<Widget> _matchProfileRows({
  required ApplicantSummaryDto a,
  required AsyncValue<PreferencesDto> preferences,
  required VoidCallback onRetry,
  required VoidCallback onAdd,
}) {
  final rows = <Widget>[];
  if (preferences.hasError && !preferences.hasValue) {
    rows.add(_RetryRow(label: 'Preferences', onRetry: onRetry));
  }
  if (preferences.value case final p?) {
    rows
      ..add(
        _SpecRow(
          label: 'Desired role',
          value: p.desiredRole == null || p.desiredRole == DesiredRole.unknown
              ? null
              : p.desiredRole!.label,
          onAdd: p.desiredRole == null ? onAdd : null,
        ),
      )
      ..add(
        _SpecRow(
          label: 'Locations',
          value: p.locations.isEmpty ? null : p.locations.join(', '),
          onAdd: p.locations.isEmpty ? onAdd : null,
        ),
      );
  }
  if (formatYears(a.yearsExperience) case final years?) {
    rows.add(_SpecRow(label: 'Experience', value: years));
  }
  if (a.noticePeriodDays != null) {
    rows.add(
      _SpecRow(label: 'Notice period', value: '${a.noticePeriodDays} days'),
    );
  }
  rows.add(_SpecRow(label: 'Current CTC', value: formatCtc(a.currentCtc)));
  if (preferences.value case final p?) {
    rows.add(
      _SpecRow(
        label: 'Expected CTC',
        value: p.expectedCtc == null ? null : formatCtc(p.expectedCtc),
        onAdd: p.expectedCtc == null ? onAdd : null,
      ),
    );
  }
  return rows;
}

class _AppearanceSelector extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentMode = ref.watch(themeModeControllerProvider);
    return SegmentedButton<ThemeMode>(
      segments: const [
        ButtonSegment(
          value: ThemeMode.system,
          label: Text('System'),
          icon: Icon(Icons.brightness_auto_outlined),
        ),
        ButtonSegment(
          value: ThemeMode.light,
          label: Text('Light'),
          icon: Icon(Icons.light_mode_outlined),
        ),
        ButtonSegment(
          value: ThemeMode.dark,
          label: Text('Dark'),
          icon: Icon(Icons.dark_mode_outlined),
        ),
      ],
      selected: {currentMode},
      onSelectionChanged: (selection) =>
          ref.read(themeModeControllerProvider.notifier).set(selection.first),
    );
  }
}

/// One row of the "Match profile" spec sheet: a plain-language label on the
/// left, and on the right either the value (mono — the app's established
/// "shows its work" data voice) or, when the field is empty, a tappable
/// caveat-amber "Add" prompt. Long values (e.g. several locations) wrap and
/// stay right-aligned rather than overflowing.
class _SpecRow extends StatelessWidget {
  const _SpecRow({required this.label, this.value, this.onAdd});

  final String label;
  final String? value;
  final VoidCallback? onAdd;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final Widget trailing;
    if (value != null) {
      trailing = Text(
        value!,
        textAlign: TextAlign.end,
        style: JobifyTypography.mono(
          fontSize: 14,
          color: theme.colorScheme.onSurface,
        ),
      );
    } else if (onAdd != null) {
      trailing = _AddFieldAction(onTap: onAdd!);
    } else {
      trailing = Text(
        '—',
        style: JobifyTypography.mono(
          fontSize: 14,
          color: theme.colorScheme.onSurfaceVariant,
        ),
      );
    }
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: JobifySpacing.sm),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const Spacer(),
          Flexible(child: trailing),
        ],
      ),
    );
  }
}

/// The caveat-amber "Add" affordance for an incomplete match-profile field —
/// jumps straight to Edit Profile rather than leaving a dead "—".
class _AddFieldAction extends StatelessWidget {
  const _AddFieldAction({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final color = isDark ? JobifyColors.caveatDark : JobifyColors.caveatLight;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(4),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Add',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: color,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(width: 2),
            Icon(Icons.arrow_forward, size: 14, color: color),
          ],
        ),
      ),
    );
  }
}

class _RetryRow extends StatelessWidget {
  const _RetryRow({required this.label, required this.onRetry});

  final String label;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: JobifySpacing.sm),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
          Text(
            "Couldn't load",
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.error,
            ),
          ),
          TextButton(onPressed: onRetry, child: const Text('Retry')),
        ],
      ),
    );
  }
}
