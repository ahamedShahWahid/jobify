#!/usr/bin/env bash
#
# new-feature.sh — start a fresh, short-lived feature branch off the LATEST
# origin/main. One feature per branch is the whole point: it's the thing that
# stops squash-merge conflicts (see WORKFLOW.md). Never restack new work on a
# branch that's already been merged.
#
# Usage:  scripts/new-feature.sh <branch-name>
# Env:    MAIN_BRANCH (default: main)
#
set -euo pipefail

MAIN="${MAIN_BRANCH:-main}"

die() {
  printf 'new-feature: %s\n' "$1" >&2
  exit 1
}

[ "$#" -ge 1 ] || die "usage: scripts/new-feature.sh <branch-name>"
name="$1"

# Name hygiene — reject the obvious foot-guns before touching git.
case "$name" in
  "$MAIN" | HEAD | "") die "refusing reserved/empty branch name '$name'" ;;
  *[[:space:]]*) die "branch name must not contain whitespace" ;;
  -*) die "branch name must not start with '-'" ;;
esac

git rev-parse --git-dir >/dev/null 2>&1 || die "not inside a git repository"

# A fresh branch should carry no stray tracked changes. Untracked files are fine
# (they ride along to the new branch).
if ! git diff --quiet || ! git diff --cached --quiet; then
  die "working tree has uncommitted tracked changes — commit or stash first"
fi

git show-ref --verify --quiet "refs/heads/$name" &&
  die "branch '$name' already exists locally"

printf 'new-feature: fetching origin/%s …\n' "$MAIN"
git fetch --quiet origin "$MAIN" ||
  die "could not fetch origin/$MAIN — is the remote reachable?"

git switch --create "$name" "origin/$MAIN"

printf '\n✓ on %s — branched from origin/%s @ %s\n' \
  "$name" "$MAIN" "$(git rev-parse --short HEAD)"
printf '  build it, commit, then before opening/refreshing the PR:\n'
printf '    scripts/sync-with-main.sh   # reconcile if main moved\n'
