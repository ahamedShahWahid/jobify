# Recruiter Phase 4 — Employer Team UI + Invitee Surface (R4 Flutter) — Plan

> Just-in-time plan for the Flutter half of R4. Source spec:
> `docs/superpowers/specs/2026-06-06-recruiter-employer-experience-design.md` §5.4, §6.1.
> Backend (Phase 3) is merged. Autonomous execution authorized.

**Goal:** An employer **Team** tab (roster + role/remove controls for owners, invite form +
pending list) and an applicant-side **Pending invitations** screen (accept/decline → role flip).

## Batch A — Data layer (`lib/data/employers/team/`)
- `member_dto.dart` — `MemberDto {userId, email?, displayName?, role, addedAt}`.
- `employer_invite_dto.dart` — `InviteDto {id, employerId, email, role, status, expiresAt,
  createdAt, invitedByUserId?}`, `MyInviteDto {id, employerId, employerName, role, expiresAt,
  createdAt}`, `AcceptResultDto {employerId, role, status}`. Plain `@JsonSerializable`.
- `employer_team_api.dart` — listMembers/addMember/changeMemberRole/removeMember,
  listInvites/createInvite/revokeInvite, listMyInvites/acceptInvite/declineInvite.
- `employer_team_repository.dart` + impl (`mapDioException`, `@Riverpod(keepAlive:true)`).
- **Commit:** `feat(app): employer team data layer (members + invites DTOs, API, repo)`

## Batch B — Controllers
- `members_controller.dart` — `@riverpod Future<List<MemberDto>> membersController(ref, employerId)`.
- `employer_invites_controller.dart` — `Future<List<InviteDto>>` family by employerId.
- `team_actions_controller.dart` — addMember/changeRole/removeMember/createInvite/revokeInvite;
  `AsyncValue.guard`; invalidate the two family controllers for the affected employerId.
- `my_invites_controller.dart` — `Future<List<MyInviteDto>>`.
- `invite_response_controller.dart` — accept (then `refreshSession()` to flip role) / decline;
  invalidate `myInvitesControllerProvider`.
- **Commit:** `feat(app): employer team + invite controllers`

## Batch C — Screens + routing
- Replace `recruiter_employer_screen.dart`: employer **switcher** (reuse `recruiterEmployersProvider`
  + `activeEmployerProvider`; auto-select single), details (name/GST/verified badge), **roster**
  (owners get change-role + remove; members read-only — owner-ness computed from the caller's own
  row by `SignedIn.userId`), **invite form** (email + role) + **pending-invites** list with revoke.
- `pending_invites_screen.dart` at `/profile/invites` — `MyInviteDto` list, Accept/Decline.
  On accept the controller refreshes the session → role flips → role-aware redirect moves the user
  into the recruiter shell.
- Applicant `profile_screen.dart`: add a **Pending invitations** ListTile (applicants only).
- `routes.dart`: `profileInvites = '/profile/invites'`; `router.dart`: nest under the profile branch.
- **Commit:** `feat(app): employer team tab + pending-invitations screen + routes`

## Batch D — Tests
- Widget: roster (owner controls vs member read-only), invite form submit + pending list render,
  invitee accept/decline. Shared `FakeEmployerTeamRepository`. `ThemeData.light(useMaterial3:true)`.
- **Commit:** `test(app): employer team + invitee widget tests`

## Definition of Done
Owner manages members + invites; applicant accepts an invite and lands in the recruiter shell.
`flutter test` + `flutter analyze` green. No regression to existing flows.
