#!/usr/bin/env bash
#
# sync-with-main.sh — reconcile the current feature branch with origin/main,
# correctly handling the SQUASH-MERGE case that a plain `git rebase` botches.
#
# Why this exists: when a PR is squash-merged, main gains ONE commit whose
# content equals your branch's earlier commits — but with a different SHA and a
# different patch-id. A plain `git rebase origin/main` therefore replays those
# already-merged commits and they conflict against the squash. The fix is
# `git rebase --onto origin/main <boundary>`, dropping the merged commits and
# replaying only the genuinely new ones. This script finds <boundary>
# automatically: the newest commit on the branch whose tree already equals
# origin/main (the squash-merge signature), and rebases only what's after it.
#
# Usage:  scripts/sync-with-main.sh [--dry-run]
# Env:    MAIN_BRANCH (default: main)
#
set -euo pipefail

MAIN="${MAIN_BRANCH:-main}"

die() {
  printf 'sync: %s\n' "$1" >&2
  exit 1
}

DRY_RUN=0
case "${1:-}" in
  --dry-run | -n) DRY_RUN=1 ;;
  "") ;;
  *) die "unknown argument: $1 (only --dry-run is supported)" ;;
esac

git rev-parse --git-dir >/dev/null 2>&1 || die "not inside a git repository"
git_dir="$(git rev-parse --git-dir)"
if [ -d "$git_dir/rebase-merge" ] || [ -d "$git_dir/rebase-apply" ]; then
  die "a rebase is already in progress — finish it or 'git rebase --abort' first"
fi

branch="$(git rev-parse --abbrev-ref HEAD)"
[ "$branch" != "$MAIN" ] || die "you're on $MAIN — run this from a feature branch"
[ "$branch" != "HEAD" ] || die "detached HEAD — check out your feature branch first"

if ! git diff --quiet || ! git diff --cached --quiet; then
  die "working tree has uncommitted changes — commit or stash first"
fi

printf 'sync: fetching origin/%s …\n' "$MAIN"
git fetch --quiet origin "$MAIN" || die "could not fetch origin/$MAIN"

# Already current? (main is an ancestor of HEAD → nothing behind us)
if git merge-base --is-ancestor "origin/$MAIN" HEAD; then
  ahead="$(git rev-list --count "origin/$MAIN..HEAD")"
  printf '✓ already on top of origin/%s (%s commit(s) ahead, 0 behind)\n' "$MAIN" "$ahead"
  exit 0
fi

# Find the squash-merge boundary: the newest branch-unique commit whose tree
# already equals origin/main. If main is exactly a squash of the branch up to
# that commit, everything AFTER it is the only genuinely-new work.
boundary=""
while IFS= read -r c; do
  if git diff --quiet "$c" "origin/$MAIN"; then
    boundary="$c"
    break
  fi
done < <(git rev-list "origin/$MAIN..HEAD")

behind="$(git rev-list --count "HEAD..origin/$MAIN")"

if [ -n "$boundary" ]; then
  if [ "$boundary" = "$(git rev-parse HEAD)" ]; then
    printf '✓ branch content already equals origin/%s — nothing new to replay.\n' "$MAIN"
    printf '  this branch looks fully merged; you can delete it:\n'
    printf '    git switch %s && git branch -d %s\n' "$MAIN" "$branch"
    exit 0
  fi
  replay="$(git rev-list --count "$boundary..HEAD")"
  printf 'sync: squash-merge detected (main moved %s commit(s) ahead).\n' "$behind"
  printf '      origin/%s already contains this branch up to %s.\n' "$MAIN" "$(git rev-parse --short "$boundary")"
  printf '      replaying only the %s commit(s) after it:\n' "$replay"
  git --no-pager log --oneline "$boundary..HEAD" | sed 's/^/        /'
  if [ "$DRY_RUN" = 1 ]; then
    printf '\n(dry run) would run: git rebase --onto origin/%s %s\n' "$MAIN" "$(git rev-parse --short "$boundary")"
    exit 0
  fi
  if ! git rebase --onto "origin/$MAIN" "$boundary"; then
    git rebase --abort
    die "rebase hit conflicts and was aborted — resolve manually (the replayed commits genuinely overlap main)"
  fi
else
  # No squash signature — ordinary divergence. A plain rebase is correct.
  printf 'sync: origin/%s moved %s commit(s) ahead; rebasing the branch onto it.\n' "$MAIN" "$behind"
  if [ "$DRY_RUN" = 1 ]; then
    printf '(dry run) would run: git rebase origin/%s\n' "$MAIN"
    exit 0
  fi
  if ! git rebase "origin/$MAIN"; then
    git rebase --abort
    die "rebase hit conflicts and was aborted — resolve manually, then re-run"
  fi
fi

printf '\n✓ %s is now on top of origin/%s — ' "$branch" "$MAIN"
printf '%s ahead, %s behind.\n' \
  "$(git rev-list --count "origin/$MAIN..HEAD")" "$(git rev-list --count "HEAD..origin/$MAIN")"
printf '  history was rewritten, so update the remote with a lease:\n'
printf '    git push --force-with-lease\n'
