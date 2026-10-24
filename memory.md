# AIPM memory

Decisions made during design (Oct 2026). Newest at the bottom.

- Hub-and-spoke: one PM session, a fleet MCP server, one persistent project team per repo. Agent Teams is not the base (single codebase, experimental).
- Worker agents are called **project teams**. Each can spawn subagents (spike, planner, researcher) scoped to its own repo.
- Teams own commits to feature branches and worktree management (create, merge, rebase), per their own CLAUDE.md and memory.md.
- Opening a pull request requires AIPM's approval. Merging to `main` requires mine.
- Cleanup (delete merged feature branches and their worktrees) is the team's job, on a "clean up" command or per its CLAUDE.md after AIPM reports the merge. AIPM is the source of truth for merges; teams never delete unmerged work.
- Budgets are in tokens, not dollars.
- Personal use on my Max plan: teams run through the unmodified `claude` CLI headless; no API key. Switch to API keys if AIPM is ever offered to others.
- Two interfaces: the PM session (Claude Code) and an AIPM Control Panel artifact in the Claude desktop app (Phase 4).
- Existing repos are adopted with `/adopt-project` (Phase 1). `reconcile` runs before every dispatch so work done outside AIPM (VS Code, Remote Control, merges I do myself) is picked up.
- Repo lives at `C:\src\AIPM`. The initial commit and push were done from WSL Ubuntu at `/mnt/c/src/AIPM`.
- The fleet server runs natively on Windows, the same environment as `C:\src`, VS Code and the Claude desktop app. One session store and one set of paths; teams use the Windows `claude` and `gh` sign-ins and Git Bash. Claude Code sessions for adopted repos never run in WSL, which has its own session store and `/mnt/c` paths.
- `main` is protected on GitHub by the "Protect main" ruleset (GitHub Pro): PR required with 0 approvals, no force push, no deletion, no bypass. All changes, docs included, go through a feature branch and PR. New and adopted repos get the same ruleset.
- In this repo, "clean up" deletes the remote and local branches of merged PRs (procedure in `CLAUDE.md`). GitHub's auto-delete-on-merge stays off so "clean up" is the only trigger.
- Cleanup uses `git branch -d` only, never `-D`, matching my global rules. `-d` refuses squash- and rebase-merged branches, so those are skipped and reported, and I delete them myself. All three GitHub merge methods stay enabled; don't restrict them.
- Gotcha: from Windows, git refuses `C:\src\AIPM` with "dubious ownership" because the folder is owned by `BUILTIN\Administrators` (created from WSL). Workaround: `git -c safe.directory=C:/src/AIPM ...`, or add it once with `git config --global --add safe.directory C:/src/AIPM`.
