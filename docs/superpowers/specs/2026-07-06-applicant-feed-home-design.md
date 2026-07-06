# Applicant Feed → Home Summary — Design Spec

**Date:** 2026-07-06
**Status:** Approved (brainstorm complete) — ready for implementation plan
**Scope:** Flutter only (`app/`). No backend changes.

---

## 1. Problem & context

The applicant shell has four tabs — Feed, Saved, Applications, Profile — and no "Home" or "Dashboard" tab. Recruiters get a dedicated `RecruiterDashboardScreen` (`lib/presentation/recruiter/recruiter_dashboard_screen.dart`) with summary stat cards and a recent-jobs list; applicants land straight on Feed (`lib/presentation/feed/feed_screen.dart`), a bare "For you" job-matches list. This asymmetry is intentional history, not a bug — the recruiter-experience spec (`2026-06-06-recruiter-employer-experience-design.md`) explicitly built the recruiter dashboard while leaving "the applicant scaffold... unchanged."

This spec reshapes Feed into the applicant's home screen by adding a summary layer above the existing job list, rather than adding a fifth tab. No new tab, no change to the four-tab nav.

## 2. What's changing

Feed keeps its `BoldScaffold` header ("For you" / "Roles matched to your profile"), its `FeedController`-driven paginated job list, and the job cards — all unchanged. Above the list, `FeedNudgeBanner` is replaced by:

1. **A "new matches" headline** (conditional) — "N new matches since your last visit," shown only when N > 0. Silence when 0; this is a signal, not a persistent UI element.
2. **A 3-tile summary row** — Applications count / Saved count / Match profile status.

### Why merge, not add a fourth tile

`FeedNudgeBanner` already renders "Upload your résumé" / "Tell us what you're looking for" driven by `resumeControllerProvider` + `preferencesControllerProvider.isComplete` — the same signal a naive "Match profile status" tile would duplicate. The match-profile tile **replaces** the banner outright: one component owns that signal, in whichever of its three states apply, instead of two components independently deciding to say the same thing.

## 3. Components

### 3.1 `lib/data/feed/feed_visit_repository.dart` (+ `feed_visit_repository_impl.dart`)

New abstract repo + impl, following the existing `data/<feature>/<repo>_repository.dart` + `_impl.dart` convention (`app/CLAUDE.md`). Wraps a single `SharedPreferences` key (`feed_last_seen_at`, ISO-8601 string), mirroring the pattern already used by `theme_mode_controller.dart`:

```dart
abstract class FeedVisitRepository {
  Future<DateTime?> getLastSeenAt();
  Future<void> setLastSeenAt(DateTime at);
}
```

`getLastSeenAt()` returns `null` on first-ever call (no stored key) — the caller must treat that as "no baseline, 0 new," never as "everything is new."

### 3.2 `lib/presentation/feed/feed_summary_controller.dart`

New `@riverpod` async controller, structurally identical to `RecruiterDashboardController` (same file layout, same MVP approximation):

```dart
class FeedSummary {
  final int applicationsCount;
  final bool applicationsApprox; // true when the 100-item page hasMore
  final int savedCount;
  final bool savedApprox;
}

class FeedSummaryController extends _$FeedSummaryController {
  Future<FeedSummary> build() async {
    final results = await Future.wait([
      ref.read(applicationsRepositoryProvider).fetchPage(limit: 100),
      ref.read(savedJobsRepositoryProvider).fetchPage(limit: 100),
    ]);
    // applicationsApprox/savedApprox = (results[i].nextCursor != null)
  }

  Future<void> refresh() async { ref.invalidateSelf(); await future; }
}
```

Independent fetch, not a reuse of `applicationsControllerProvider`/`savedControllerProvider` — mirrors `RecruiterDashboardController`'s own independence from `RecruiterJobsController`, so a limit change here never affects the real Applications/Saved tab screens (or vice versa). Documented approximation: counts above 100 show "100+", identical in spirit to the recruiter dashboard's own "MVP-documented approximation... acceptable for MVP" comment.

### 3.3 `lib/presentation/feed/feed_summary_row.dart`

Three tiles in a `Row`, visually mirroring `RecruiterDashboardScreen`'s `_SummaryCard` (icon, mono count, label) for cross-role consistency, and reusing the "Match profile" card language from the profile-screen redesign (mono values, caveat-amber for actionable gaps):

- **Applications tile** — watches `feedSummaryControllerProvider`; count in mono; loading → neutral skeleton tile; error → quiet retry icon (no crash, no block on the job list below); tap → `context.go(Routes.applications)`.
- **Saved tile** — same shape, watches the same controller, tap → `context.go(Routes.saved)`.
- **Match-profile tile** — watches `resumeControllerProvider` + `preferencesControllerProvider` directly (same two providers `FeedNudgeBanner` watched; same "only decide from resolved data" guard — never renders off a loading or failed fetch, per the existing code comment). Three states:
  - No résumé → amber tile, "Upload résumé," tap → `context.push(Routes.resume)`.
  - Résumé present, `preferences.isComplete == false` → amber tile, "Finish your profile," tap → `context.push(Routes.preferences, extra: resume)` (identical navigation to the old banner).
  - Both complete → quiet ink-soft tile, checkmark icon, "Profile complete," tap → `context.go(Routes.profile)`.
  - Either provider unresolved → neutral placeholder tile (not blank, not the wrong state).

### 3.4 `feed_screen.dart` (modified)

`_FeedScreenState` gains one-shot visit-stamping in `initState`:

```dart
DateTime? _lastSeenAt;

@override
void initState() {
  super.initState();
  _scroll.addListener(...); // unchanged
  unawaited(_stampVisit());
}

Future<void> _stampVisit() async {
  final repo = ref.read(feedVisitRepositoryProvider);
  final prev = await repo.getLastSeenAt();
  if (mounted) setState(() => _lastSeenAt = prev);
  await repo.setLastSeenAt(DateTime.now());
}
```

This runs exactly once per screen mount (not tied to Riverpod rebuilds — `FeedController` refreshing or loading more must NOT re-stamp the visit, or the count would only ever reflect the last pull-to-refresh instead of the last time the user actually opened the app). `build()` computes the headline count by comparing each loaded item's `item.match.surfacedAt` (nullable `DateTime` on `MatchSummaryDto`, NOT on `FeedItemDto` directly) against the captured `_lastSeenAt`; `null` `_lastSeenAt` (first-ever visit) → count is 0, headline never renders.

**Explicit approximation:** this count only sees whatever `FeedController` has currently loaded (first page, ordered by match score — NOT recency), so a newly-surfaced but low-scoring match beyond the loaded page(s) won't be counted until the user scrolls further. Confirmed acceptable — same MVP-approximation spirit as §3.2 and the existing recruiter dashboard.

### 3.5 Delete `lib/presentation/feed/feed_nudge_banner.dart`

Superseded by 3.3. No separate test file exists for it — its behavior is tested inline in `feed_screen_test.dart` (see §5).

## 4. Error handling

- Summary row count tiles degrade independently: a failed `feedSummaryControllerProvider` fetch shows a quiet inline retry on those two tiles only — never blocks the match-profile tile or the job list beneath.
- Match-profile tile: unchanged semantics from the old banner — renders nothing (not a wrong-state flash) until both `resumeControllerProvider` and `preferencesControllerProvider` resolve.
- New-matches headline: purely derived from already-resolved `FeedController` state — if `FeedController` itself is loading or erroring, the headline simply doesn't render; no new failure mode.

## 5. Testing

- **New `test/unit/presentation/feed/feed_summary_controller_test.dart`** — counts, and the `hasMore` → `*Approx` flag, mirroring the existing recruiter dashboard controller test shape.
- **New `test/widget/feed_summary_row_test.dart`** — the match-profile tile's three states (no résumé / incomplete prefs / complete) and all three tiles' tap-through routes.
- **`test/widget/feed_screen_test.dart` (existing, updated)**:
  - Tests `'shows upload nudge when no resume'` and `'shows preferences nudge when resume exists but incomplete'` — assertions change from banner text to the amber tile's label text, same underlying condition.
  - Test `'no banner while the resume fetch is still pending'` → rename/assert the tile shows its neutral placeholder, not the amber or complete state.
  - Test `'no banner when the resume fetch throws'` → same as above.
  - Test `'no banner when resume and preferences are complete'` → **semantics change**: this used to assert absence of nudge text; now it must assert the tile shows quiet "Profile complete" (there is always a tile present, it just isn't actionable when complete).
  - New case: new-matches headline appears when a fake `FeedVisitRepository` returns a past `lastSeenAt` and at least one loaded item's `match.surfacedAt` is after it; absent when `lastSeenAt` is `null` (first visit) or all items are older.

## 6. Out of scope

- A fifth "Home" tab (explicitly rejected in favor of reshaping Feed).
- A backend aggregate/count endpoint for applications, saved jobs, or feed matches (client-side summed, matching existing MVP precedent).
- Exact, non-approximate "new matches" counting across the applicant's entire feed (would need either a full client-side page-through or a new backend endpoint — deferred).
- Any change to the recruiter dashboard or recruiter shell.
