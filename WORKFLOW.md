# Branch & merge workflow

The short version: **one short-lived branch per feature, branched off the latest
`origin/main`, merged promptly, then deleted.** Don't stack a second feature on a
branch that's already been (or is about to be) merged.

Two helper scripts in `scripts/` make this the path of least resistance.

## Why this exists

We use **squash merges** (GitHub's default "Squash and merge"). A squash collapses
all of a branch's commits into **one** new commit on `main` — with a different SHA
*and* a different patch-id than any of the originals.

That's fine until you keep working on the **same long-lived branch** after part of
it was merged. Now:

- `main` has the squash commit `S` (= your commits `C1..C9` combined).
- your branch still has `C1..C9` as real commits, plus new `C10, C11`.

A plain `git rebase origin/main` replays `C1..C9` on top of `S`, and since `S`
already changed those same lines, **every one of them conflicts**. This is the
"again, merge conflicts" loop. It is not a content problem — it's a history-shape
problem.

The fix is `git rebase --onto origin/main <boundary>`, which drops the
already-merged commits and replays only the genuinely new ones. `sync-with-main.sh`
finds `<boundary>` automatically and does this for you.

The deeper fix is to **not be in that situation**: start each feature on a fresh
branch (`new-feature.sh`) so a merge ends the branch's life instead of leaving a
half-merged stump to build on.

## The scripts

### `scripts/new-feature.sh <branch-name>`
Fetches `origin/main` and creates `<branch-name>` from it. Refuses to run with a
dirty tree or a name that already exists.

```sh
scripts/new-feature.sh feat/notifications-digest
```

### `scripts/sync-with-main.sh [--dry-run]`
Run from a feature branch when `main` has moved. It:

1. fetches `origin/main`;
2. if your branch is already on top of it, says so and stops;
3. detects the **squash-merge** case (the newest commit on your branch whose tree
   already equals `origin/main`) and rebases **only the commits after it** with
   `git rebase --onto`;
4. otherwise does an ordinary `git rebase origin/main`;
5. on conflicts, **aborts cleanly** and tells you to resolve by hand — it never
   leaves you mid-rebase or auto-resolves.

```sh
scripts/sync-with-main.sh --dry-run   # show the plan, change nothing
scripts/sync-with-main.sh             # do it
git push --force-with-lease           # history was rewritten
```

`--force-with-lease` (not `--force`) so you can't clobber someone else's push.

## The loop

```sh
scripts/new-feature.sh feat/x      # 1. fresh branch off latest main
# … build, commit …
scripts/sync-with-main.sh          # 2. (only if main moved) reconcile
git push -u origin feat/x          # 3. push
gh pr create --base main           # 4. open PR, squash-merge it
git switch main && git pull        # 5. after merge: back to main
git branch -d feat/x               #    delete the merged branch — don't reuse it
```

## Limitations

- `sync-with-main.sh`'s squash detection relies on `main`'s tree exactly matching
  your branch at the boundary commit. If `main` also gained **unrelated** commits
  since you branched, that exact match won't hold and the script falls back to a
  plain rebase — which can conflict against the squash. Resolve those by hand, or
  rebase `--onto origin/main <last-merged-commit>` yourself.
- Override the trunk name with `MAIN_BRANCH=master scripts/…` if needed.
