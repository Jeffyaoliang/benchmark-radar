---
name: maintainer-local-clean
description: Clean stale local git state in the Benchmark Radar checkout after pulling main. Use when the maintainer asks to pull and clear stale branches, worktrees, or remote-tracking refs.
---

# Maintainer local clean

This repo squash-merges, so a merged branch is not an ancestor of `main`. Prove
merges through GitHub, not through `git branch --merged`.

## Steps

1. Pull `main`: `git pull --ff-only` on `main`, then `git fetch --all --prune`.
2. List candidates: `git worktree list`, `git branch -vv`, and
   `git for-each-ref refs/remotes`.
3. For each branch, worktree, or remote-tracking ref, find its PR number
   (branch name, or `gh pr list --state all --head <branch>`). Read its state
   with `gh pr view <n> --json state,headRefOid`.
4. Classify:
   - `MERGED`: remove the local branch, worktree, and tracking ref.
   - `CLOSED` without merge: when you remove the ref, tag its tip first with
     `git tag legacy/<branch> <ref>` (local only, never pushed). Do this
     automatically and do not list it as a finding. If the ref stays, add no tag.
   - `OPEN`: keep.
   - `star-history` (any remote): automation branch. Always keep, never report.
   - Any other branch with no PR: keep, and report it.
5. Before removing a worktree, check `git -C <path> status --short` is empty.
   A worktree whose directory is gone is removed by `git worktree prune`.
6. Present the plan and wait for approval. Remove in this order: worktrees,
   local branches, remote-tracking refs.

## Constraints

- Delete only local state. Never run `git push origin --delete` unless the
  maintainer names the remote branch.
- Keep all tags, including `legacy/*`.
- Keep ignored build artifacts (`site/*`, `data/catalog/*`, `.venv`, `out/`).
  They regenerate from the build, but a rebuild is slow.
- Do not touch `main`, the current branch, or a branch checked out in a
  worktree you are keeping.
- If a hook blocks `git branch -d` or `-dr`, give the maintainer the exact
  command to run. Do not bypass the hook with `update-ref`.
