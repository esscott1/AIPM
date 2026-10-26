# AIPM repo — build rules

This repo builds AIPM, a program-manager agent over my other Claude Code repos. Read `docs/architecture.md` and `docs/roadmap.md` before starting work.

## Current phase

Phase 1 (scaffold). Work only on unchecked items in `docs/roadmap.md` under Phase 1 unless told otherwise. Tick items off in the roadmap as they are done.

## Working rules

- Every change, docs included, goes on a feature branch and reaches `main` only through a pull request. Never commit directly to `main`. I merge PRs.
- Keep `docs/architecture.md` true: if a design decision changes, update it in the same PR.
- Record decisions and gotchas in `memory.md`.
- The fleet server must never read, store or forward Claude or GitHub credentials. Teams run through the unmodified `claude` CLI signed in with my own account.
- Teams run on my claude.ai sign-in. Never run a team on an API key unless I confirm twice in this session: ask and explain the billing change, then ask again before the first dispatch.
- Never use `bypassPermissions`.
- Secrets and runtime state stay out of git: `projects.yaml`, `fleet/sessions.json`, `fleet/jobs/`, `.env`.

## When I say I merged a PR

1. Confirm it merged: `gh pr view <number> --json state,mergeCommit` shows `MERGED`.
2. Run `git fetch --prune origin`, switch to `main` and `git pull --ff-only`, then confirm `git rev-parse main` equals `git rev-parse origin/main`.
3. If both checks pass, ask me whether to clean up. Run "clean up" below only after I say yes.
4. If either check fails, tell me what you found and don't offer to clean up.

## "clean up" command

When I say "clean up", delete the feature branches whose PRs I have merged, on the remote and locally:

1. `git fetch --prune origin`, then switch to `main` and `git pull --ff-only`.
2. List merged PRs with `gh pr list --state merged --base main --json number,headRefName,headRefOid`; their branches that still exist are the candidates.
3. Delete a candidate only if its tip (remote, and local if present) equals the PR's `headRefOid` and `git log main..<branch>` is empty. Skip the rest and report them: a branch with commits after the merge, or one that was squash- or rebase-merged, which I delete myself.
4. Before deleting, list the branches to delete and to skip.
5. Remove any worktree on that branch (`git worktree remove`), then delete the remote branch (`git push origin --delete <branch>`) and the local one with `git branch -d <branch>`. Never use `git branch -D`; if `-d` refuses, skip the branch and report it.
6. Never delete `main`, a branch with an open PR, or a branch with no merged PR.
7. Report what was deleted and what was skipped, with the reason.
