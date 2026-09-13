// ignore_for_file: directives_ordering

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/core/l10n/l10n_ext.dart';
import 'package:jobify_app/data/auth/user_role.dart';
import 'package:jobify_app/data/me/me_dto.dart';
import 'package:jobify_app/data/preferences/desired_role.dart';
import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';
import 'package:jobify_app/presentation/auth/current_role_provider.dart';
import 'package:jobify_app/presentation/preferences/desired_role_label.dart';
import 'package:jobify_app/presentation/preferences/preferences_controller.dart';
import 'package:jobify_app/presentation/profile/ctc_format.dart';
import 'package:jobify_app/presentation/profile/me_controller.dart';
import 'package:jobify_app/presentation/profile/package_info_provider.dart';
import 'package:jobify_app/presentation/profile/sign_out_controller.dart';
import 'package:jobify_app/presentation/routing/locale_controller.dart';
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
    final l10n = context.l10n;

    return BoldScaffold(
      header: BoldHeader(
        title: l10n.profileTitle,
        trailing: TextButton(
          onPressed: () => context.go(Routes.profileEdit),
          child: Text(l10n.profileEditButton),
        ),
      ),
      child: AsyncValueWidget(
        value: me,
        onRetry: () => ref.read(meControllerProvider.notifier).refresh(),
        data: (data) {
          var arriveIndex = 0;
          Widget arrive(Widget child) =>
              Arrive(index: arriveIndex++, child: child);

          final rows =
              data.applicant != null
                  ? _matchProfileRows(
                    context: context,
                    a: data.applicant!,
                    preferences: preferences,
                    onRetry:
                        () => ref.invalidate(preferencesControllerProvider),
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
                      data.displayName ?? data.email ?? l10n.profileTitle,
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
                      title: Text(l10n.profileHiringCtaTitle),
                      subtitle: Text(l10n.profileHiringCtaSubtitle),
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
                      Text(
                        l10n.profileMatchProfileHeading,
                        style: theme.textTheme.titleMedium,
                      ),
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
                    Text(
                      l10n.profileAccountHeading,
                      style: theme.textTheme.titleMedium,
                    ),
                    const SizedBox(height: JobifySpacing.sm),
                    Card(
                      clipBehavior: Clip.antiAlias,
                      child: Column(
                        children: [
                          ListTile(
                            leading: const Icon(Icons.description_outlined),
                            title: Text(l10n.resumeTitle),
                            subtitle: Text(l10n.profileResumeSubtitle),
                            onTap: () => context.go(Routes.resume),
                          ),
                          Divider(
                            height: 1,
                            color: theme.colorScheme.outlineVariant,
                          ),
                          ListTile(
                            leading: const Icon(Icons.notifications_outlined),
                            title: Text(l10n.notificationsTitle),
                            subtitle: Text(l10n.profileNotificationsSubtitle),
                            onTap: () => context.go(Routes.notifications),
                          ),
                          if (isApplicant) ...[
                            Divider(
                              height: 1,
                              color: theme.colorScheme.outlineVariant,
                            ),
                            ListTile(
                              leading: const Icon(Icons.mail_outline),
                              title: Text(l10n.invitesTitle),
                              subtitle: Text(l10n.profileInvitesSubtitle),
                              onTap: () => context.go(Routes.profileInvites),
                            ),
                          ],
                          Divider(
                            height: 1,
                            color: theme.colorScheme.outlineVariant,
                          ),
                          ListTile(
                            leading: const Icon(Icons.shield_outlined),
                            title: Text(l10n.privacyTitle),
                            subtitle: Text(l10n.profilePrivacySubtitle),
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
                    Text(
                      l10n.profileAppearanceHeading,
                      style: theme.textTheme.titleMedium,
                    ),
                    const SizedBox(height: JobifySpacing.sm),
                    _AppearanceSelector(),
                  ],
                ),
              ),
              const SizedBox(height: JobifySpacing.xl),
              arrive(
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      l10n.profileLanguageLabel,
                      style: theme.textTheme.titleMedium,
                    ),
                    const SizedBox(height: JobifySpacing.sm),
                    _LanguageSelector(preferences: preferences),
                  ],
                ),
              ),
              const SizedBox(height: JobifySpacing.xxl),
              arrive(
                OutlinedButton(
                  onPressed:
                      signOut.isLoading
                          ? null
                          : () => _confirmSignOut(context, ref),
                  child: Text(
                    signOut.isLoading
                        ? l10n.profileSigningOutButton
                        : l10n.profileSignOutButton,
                  ),
                ),
              ),
              const SizedBox(height: JobifySpacing.xxl),
              ref
                  .watch(packageInfoProvider)
                  .when(
                    data:
                        (info) => Center(
                          child: Text(
                            l10n.profileVersionLabel(
                              info.version,
                              info.buildNumber,
                            ),
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
    final l10n = ctx.l10n;
    final ok = await showDialog<bool>(
      context: ctx,
      builder:
          (c) => AlertDialog(
            title: Text(l10n.profileSignOutDialogTitle),
            content: Text(l10n.profileSignOutDialogBody),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(c, false),
                child: Text(l10n.commonCancel),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(c, true),
                child: Text(l10n.profileSignOutButton),
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
  required BuildContext context,
  required ApplicantSummaryDto a,
  required AsyncValue<PreferencesDto> preferences,
  required VoidCallback onRetry,
  required VoidCallback onAdd,
}) {
  final l10n = context.l10n;
  final rows = <Widget>[];
  if (preferences.hasError && !preferences.hasValue) {
    rows.add(
      _RetryRow(label: l10n.profileRetryPreferencesLabel, onRetry: onRetry),
    );
  }
  if (preferences.value case final p?) {
    rows
      ..add(
        _SpecRow(
          label: l10n.preferencesDesiredRoleLabel,
          value:
              p.desiredRole == null || p.desiredRole == DesiredRole.unknown
                  ? null
                  : desiredRoleLabel(context, p.desiredRole!),
          onAdd: p.desiredRole == null ? onAdd : null,
        ),
      )
      ..add(
        _SpecRow(
          label: l10n.preferencesLocationsLabel,
          value: p.locations.isEmpty ? null : p.locations.join(', '),
          onAdd: p.locations.isEmpty ? onAdd : null,
        ),
      );
  }
  if (formatYearsNumber(a.yearsExperience) case final years?) {
    rows.add(
      _SpecRow(
        label: l10n.profileExperienceLabel,
        value: l10n.profileYearsExperienceSuffix(years),
      ),
    );
  }
  if (a.noticePeriodDays != null) {
    rows.add(
      _SpecRow(
        label: l10n.profileNoticePeriodLabel,
        value: l10n.profileNoticePeriodDaysValue(a.noticePeriodDays!),
      ),
    );
  }
  rows.add(
    _SpecRow(
      label: l10n.profileCurrentCtcLabel,
      value: formatCtc(a.currentCtc),
    ),
  );
  if (preferences.value case final p?) {
    rows.add(
      _SpecRow(
        label: l10n.profileExpectedCtcLabel,
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
    final l10n = context.l10n;
    return SegmentedButton<ThemeMode>(
      segments: [
        ButtonSegment(
          value: ThemeMode.system,
          label: Text(l10n.profileAppearanceSystem),
          icon: const Icon(Icons.brightness_auto_outlined),
        ),
        ButtonSegment(
          value: ThemeMode.light,
          label: Text(l10n.profileAppearanceLight),
          icon: const Icon(Icons.light_mode_outlined),
        ),
        ButtonSegment(
          value: ThemeMode.dark,
          label: Text(l10n.profileAppearanceDark),
          icon: const Icon(Icons.dark_mode_outlined),
        ),
      ],
      selected: {currentMode},
      onSelectionChanged:
          (selection) => ref
              .read(themeModeControllerProvider.notifier)
              .set(selection.first),
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
          const SizedBox(width: JobifySpacing.lg),
          // Expanded + end-Align, not Spacer + Flexible: that pair splits the
          // free width 50/50 and a loose Flexible parks the value at mid-row.
          Expanded(
            child: Align(
              alignment: AlignmentDirectional.topEnd,
              child: trailing,
            ),
          ),
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
              context.l10n.profileAddFieldAction,
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

/// English/Hindi language switcher. Tapping a segment (a) optimistically
/// flips the app locale so the UI re-renders immediately, then (b) saves
/// through the shared preferences controller's `submit` path, seeding every
/// other field from the currently-loaded preferences (full-form contract —
/// see `PreferencesUpdateDto`). On save failure, `PreferencesController.
/// submit` itself restores the pre-tap locale (see its rollback branch).
class _LanguageSelector extends ConsumerWidget {
  const _LanguageSelector({required this.preferences});

  final AsyncValue<PreferencesDto> preferences;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final locale = ref.watch(localeControllerProvider);
    final l10n = context.l10n;
    final selected = locale?.languageCode ?? 'en';
    return SegmentedButton<String>(
      segments: [
        ButtonSegment(value: 'en', label: Text(l10n.profileLanguageEnglish)),
        ButtonSegment(value: 'hi', label: Text(l10n.profileLanguageHindi)),
      ],
      selected: {selected},
      onSelectionChanged:
          preferences.hasValue
              ? (selection) =>
                  _onChanged(ref, preferences.requireValue, selection.first)
              : null,
    );
  }

  Future<void> _onChanged(
    WidgetRef ref,
    PreferencesDto current,
    String language,
  ) async {
    ref.read(localeControllerProvider.notifier).setFromLanguage(language);
    final update = PreferencesUpdateDto(
      desiredRole: current.desiredRole,
      locations: current.locations,
      expectedCtc:
          current.expectedCtc == null
              ? null
              : num.tryParse(current.expectedCtc!),
      language: language,
    );
    await ref.read(preferencesControllerProvider.notifier).submit(update);
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
            context.l10n.profileRetryFailedLabel,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.error,
            ),
          ),
          TextButton(onPressed: onRetry, child: Text(context.l10n.commonRetry)),
        ],
      ),
    );
  }
}
