import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/auth/auth_state.dart';
import 'package:kpa_app/data/employers/employer_dto.dart';
import 'package:kpa_app/data/employers/team/employer_invite_dto.dart';
import 'package:kpa_app/data/employers/team/member_dto.dart';
import 'package:kpa_app/presentation/auth/auth_providers.dart';
import 'package:kpa_app/presentation/recruiter/active_employer_provider.dart';
import 'package:kpa_app/presentation/recruiter/team/employer_invites_controller.dart';
import 'package:kpa_app/presentation/recruiter/team/members_controller.dart';
import 'package:kpa_app/presentation/recruiter/team/team_actions_controller.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';
import 'package:kpa_app/presentation/widgets/async_value_widget.dart';

String _roleLabel(String role) => role == 'owner' ? 'Owner' : 'Member';

class RecruiterEmployerScreen extends ConsumerWidget {
  const RecruiterEmployerScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final employers = ref.watch(recruiterEmployersProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Team')),
      body: AsyncValueWidget<List<EmployerDto>>(
        value: employers,
        onRetry: () => ref.invalidate(recruiterEmployersProvider),
        isEmpty: (list) => list.isEmpty,
        empty: () => const Center(
          child: Padding(
            padding: EdgeInsets.all(KpaSpacing.xl),
            child: Text('You are not part of any company yet.'),
          ),
        ),
        data: (list) {
          // Reconcile the (keepAlive) active employer against the current list:
          // if it dropped out (e.g. membership removed by another owner), fall
          // back to the first so the switcher's initialValue always matches an
          // item — a DropdownButtonFormField asserts otherwise.
          final stored = ref.watch(activeEmployerProvider);
          final active = stored != null && list.any((e) => e.id == stored.id)
              ? stored
              : list.first;
          return _TeamView(employers: list, active: active);
        },
      ),
    );
  }
}

class _TeamView extends ConsumerWidget {
  const _TeamView({required this.employers, required this.active});

  final List<EmployerDto> employers;
  final EmployerDto active;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final members = ref.watch(membersControllerProvider(active.id));
    final auth = ref.watch(authStateProvider);
    final myUserId = auth is SignedIn ? auth.userId : null;

    return RefreshIndicator(
      onRefresh: () async {
        ref
          ..invalidate(membersControllerProvider(active.id))
          ..invalidate(employerInvitesControllerProvider(active.id));
      },
      child: ListView(
        padding: const EdgeInsets.all(KpaSpacing.lg),
        children: [
          if (employers.length > 1) ...[
            _EmployerSwitcher(employers: employers, active: active),
            const SizedBox(height: KpaSpacing.lg),
          ],
          // --- Company details ---
          Card(
            child: Padding(
              padding: const EdgeInsets.all(KpaSpacing.lg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          active.name,
                          style: theme.textTheme.titleLarge,
                        ),
                      ),
                      if (active.isVerified)
                        Icon(
                          Icons.verified,
                          size: 20,
                          color: theme.colorScheme.primary,
                        ),
                    ],
                  ),
                  if (active.gst != null) ...[
                    const SizedBox(height: KpaSpacing.xs),
                    Text(
                      'GST: ${active.gst}',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: KpaSpacing.xl),
          Text('Members', style: theme.textTheme.titleMedium),
          const SizedBox(height: KpaSpacing.sm),
          AsyncValueWidget<List<MemberDto>>(
            value: members,
            onRetry: () => ref.invalidate(membersControllerProvider(active.id)),
            data: (roster) {
              final me = _findMe(roster, myUserId);
              final amOwner = me?.isOwner ?? false;
              return Column(
                children: [
                  for (final m in roster)
                    _MemberTile(
                      member: m,
                      employerId: active.id,
                      amOwner: amOwner,
                      isSelf: m.userId == myUserId,
                    ),
                  if (amOwner) ...[
                    const SizedBox(height: KpaSpacing.xl),
                    Text(
                      'Invite a recruiter',
                      style: theme.textTheme.titleMedium,
                    ),
                    const SizedBox(height: KpaSpacing.sm),
                    _InviteForm(employerId: active.id),
                  ],
                  const SizedBox(height: KpaSpacing.xl),
                  Text(
                    'Pending invitations',
                    style: theme.textTheme.titleMedium,
                  ),
                  const SizedBox(height: KpaSpacing.sm),
                  _PendingInvites(employerId: active.id, amOwner: amOwner),
                ],
              );
            },
          ),
        ],
      ),
    );
  }

  MemberDto? _findMe(List<MemberDto> roster, String? myUserId) {
    for (final m in roster) {
      if (m.userId == myUserId) return m;
    }
    return null;
  }
}

class _EmployerSwitcher extends ConsumerWidget {
  const _EmployerSwitcher({required this.employers, required this.active});

  final List<EmployerDto> employers;
  final EmployerDto active;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return DropdownButtonFormField<String>(
      initialValue: active.id,
      decoration: const InputDecoration(labelText: 'Company'),
      items: [
        for (final e in employers)
          DropdownMenuItem(value: e.id, child: Text(e.name)),
      ],
      onChanged: (id) {
        if (id == null) return;
        ref.read(activeEmployerProvider.notifier).select(
              employers.firstWhere((e) => e.id == id),
            );
      },
    );
  }
}

class _MemberTile extends ConsumerWidget {
  const _MemberTile({
    required this.member,
    required this.employerId,
    required this.amOwner,
    required this.isSelf,
  });

  final MemberDto member;
  final String employerId;
  final bool amOwner;
  final bool isSelf;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final name = member.displayName ?? member.email ?? 'Member';
    final subtitle = _roleLabel(member.role) + (isSelf ? ' · You' : '');
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: const CircleAvatar(child: Icon(Icons.person_outline)),
      title: Text(name),
      subtitle: Text(subtitle),
      // Owners manage OTHERS, never themselves: self change-role/remove via this
      // menu would strand the UI (stale switcher, 403'd roster refetch) and a
      // self-demotion wouldn't leave the recruiter shell. Self-leave is a
      // separate deferred feature.
      trailing: (amOwner && !isSelf)
          ? _MemberMenu(member: member, employerId: employerId)
          : null,
    );
  }
}

class _MemberMenu extends ConsumerWidget {
  const _MemberMenu({required this.member, required this.employerId});

  final MemberDto member;
  final String employerId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return PopupMenuButton<String>(
      onSelected: (action) => _onSelected(context, ref, action),
      itemBuilder: (_) => [
        if (member.isOwner)
          const PopupMenuItem(value: 'demote', child: Text('Change to member'))
        else
          const PopupMenuItem(value: 'promote', child: Text('Make owner')),
        const PopupMenuItem(value: 'remove', child: Text('Remove')),
      ],
    );
  }

  Future<void> _onSelected(
    BuildContext context,
    WidgetRef ref,
    String action,
  ) async {
    if (ref.read(teamActionsControllerProvider).isLoading) return;
    final messenger = ScaffoldMessenger.of(context);
    final notifier = ref.read(teamActionsControllerProvider.notifier);
    bool ok;
    if (action == 'remove') {
      final confirmed = await _confirm(
        context,
        title: 'Remove member?',
        body: 'They will lose access to this company.',
      );
      if (!confirmed) return;
      ok = await notifier.removeMember(employerId, member.userId);
    } else {
      final role = action == 'promote' ? 'owner' : 'member';
      ok = await notifier.changeRole(employerId, member.userId, role: role);
    }
    if (!ok) {
      messenger.showSnackBar(
        SnackBar(content: Text(_actionError(ref))),
      );
    }
  }
}

class _InviteForm extends ConsumerStatefulWidget {
  const _InviteForm({required this.employerId});
  final String employerId;

  @override
  ConsumerState<_InviteForm> createState() => _InviteFormState();
}

class _InviteFormState extends ConsumerState<_InviteForm> {
  final _email = TextEditingController();
  String _role = 'member';

  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final messenger = ScaffoldMessenger.of(context);
    final email = _email.text.trim();
    if (email.isEmpty || !email.contains('@')) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Enter a valid email.')),
      );
      return;
    }
    final ok = await ref
        .read(teamActionsControllerProvider.notifier)
        .createInvite(widget.employerId, email: email, role: _role);
    if (!mounted) return;
    if (ok) {
      _email.clear();
      messenger.showSnackBar(
        SnackBar(content: Text('Invitation sent to $email.')),
      );
    } else {
      messenger.showSnackBar(SnackBar(content: Text(_actionError(ref))));
    }
  }

  @override
  Widget build(BuildContext context) {
    final busy = ref.watch(teamActionsControllerProvider).isLoading;
    return Column(
      children: [
        TextField(
          controller: _email,
          keyboardType: TextInputType.emailAddress,
          decoration: const InputDecoration(labelText: 'Email'),
        ),
        const SizedBox(height: KpaSpacing.sm),
        Row(
          children: [
            Expanded(
              child: DropdownButtonFormField<String>(
                initialValue: _role,
                decoration: const InputDecoration(labelText: 'Role'),
                items: const [
                  DropdownMenuItem(value: 'member', child: Text('Member')),
                  DropdownMenuItem(value: 'owner', child: Text('Owner')),
                ],
                onChanged: (v) => setState(() => _role = v ?? 'member'),
              ),
            ),
            const SizedBox(width: KpaSpacing.md),
            FilledButton(
              onPressed: busy ? null : _submit,
              child: const Text('Send'),
            ),
          ],
        ),
      ],
    );
  }
}

class _PendingInvites extends ConsumerWidget {
  const _PendingInvites({required this.employerId, required this.amOwner});

  final String employerId;
  final bool amOwner;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final invites = ref.watch(employerInvitesControllerProvider(employerId));
    return AsyncValueWidget<List<InviteDto>>(
      value: invites,
      onRetry: () =>
          ref.invalidate(employerInvitesControllerProvider(employerId)),
      isEmpty: (list) => list.isEmpty,
      empty: () => Padding(
        padding: const EdgeInsets.symmetric(vertical: KpaSpacing.sm),
        child: Text(
          'No pending invitations.',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
        ),
      ),
      data: (list) => Column(
        children: [
          for (final inv in list)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.mail_outline),
              title: Text(inv.email),
              subtitle: Text('${_roleLabel(inv.role)} · Pending'),
              trailing: amOwner
                  ? IconButton(
                      icon: const Icon(Icons.close),
                      tooltip: 'Revoke',
                      onPressed: () => _revoke(context, ref, inv.id),
                    )
                  : null,
            ),
        ],
      ),
    );
  }

  Future<void> _revoke(
    BuildContext context,
    WidgetRef ref,
    String inviteId,
  ) async {
    if (ref.read(teamActionsControllerProvider).isLoading) return;
    final messenger = ScaffoldMessenger.of(context);
    final ok = await ref
        .read(teamActionsControllerProvider.notifier)
        .revokeInvite(employerId, inviteId);
    if (!ok) {
      messenger.showSnackBar(SnackBar(content: Text(_actionError(ref))));
    }
  }
}

Future<bool> _confirm(
  BuildContext context, {
  required String title,
  required String body,
}) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (c) => AlertDialog(
      title: Text(title),
      content: Text(body),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(c, false),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(c, true),
          child: const Text('Confirm'),
        ),
      ],
    ),
  );
  return ok ?? false;
}

/// Friendly message for a failed team action, mapping known backend slugs.
String _actionError(WidgetRef ref) {
  final err = ref.read(teamActionsControllerProvider).error;
  if (err is ApiException) {
    return switch (err.detail) {
      'last_owner' => 'A company must keep at least one owner.',
      'already_a_member' => 'That person is already on the team.',
      'user_not_found' =>
        'No KPA account uses that email — send an invite instead.',
      'invite_already_pending' =>
        'An invitation is already pending for that email.',
      _ => 'Something went wrong. Try again.',
    };
  }
  return 'Something went wrong. Try again.';
}
