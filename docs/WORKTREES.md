# Multi-session worktree layout

This repo is worked on by multiple concurrent agents/sessions. Without
isolation, one session's `git checkout` flips another session's
working tree and clobbers in-flight files.

The fix: **one git worktree per session-or-branch.** They share the
`.git/` object store (so commits + fetches stay in sync) but each has
its own working tree.

## Layout

```
~/southbrook-v19cr/         primary worktree — feature/module-0-skeleton
                             (the "module track" — Modules 0..9 + API)
~/southbrook-v19cr-audit/   feature/configurator-attribute-audit-v1
                             (the "audit track" — configurator-attribute
                             audit Phases 2A–2I)
~/southbrook-v19cr-<other>/  add as needed for new feature branches
```

## Create

```bash
cd ~/southbrook-v19cr
git worktree add ~/southbrook-v19cr-<branch-shortname> <branch-name>
# e.g.
git worktree add ~/southbrook-v19cr-portal-v2 feature/portal-v2
```

## Each session works in its own dir

Every Claude / agent / IDE / terminal session sets `cwd` to one
worktree. None of them ever cross-checkout.

```bash
# Session A
cd ~/southbrook-v19cr           # module track
# Session B
cd ~/southbrook-v19cr-audit     # audit track
```

Commits and pushes from any worktree update the shared `.git/`
object store; `git fetch` once + you're all current.

## Cleanup

```bash
git worktree remove ~/southbrook-v19cr-<short>   # detached state
git worktree prune                               # purge stale entries
git branch -d feature/<branch>                   # delete after merge
```

## Why this matters

The original symptom was branch-flip mid-session: while editing files
on `feature/module-0-skeleton`, another session would run
`git checkout feature/configurator-attribute-audit-v1` and my working
tree would silently swap, losing untracked files (or worse, mixing
them across branches).

Worktrees solve it because the working tree is per-directory, not
per-branch. Two sessions can each be on a different branch
simultaneously without contention.

## Diagnostic

```bash
git worktree list   # shows all active worktrees + their HEADs
ps aux | grep claude   # confirms no two sessions share a worktree
```
