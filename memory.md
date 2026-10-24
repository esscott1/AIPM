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
- When I report a merge, Claude confirms it through `gh`, syncs `main` with `origin/main`, then asks before cleaning up (procedure in `CLAUDE.md`).
- `projects.yaml` is local state, not in git: fleet tools write it (adopt, create, pause, resume, retire), so committing it would need a PR for every pause. `projects.example.yaml` documents the format. Each field has one home: the registry in `projects.yaml`, `session_id` and `last_seen_commit` in `fleet/sessions.json`. Accepted downside: lose the machine, re-adopt each repo.
- The registry allows only `plan` and `acceptEdits` permission modes and rejects `bypassPermissions`. The `claude` CLI also offers `auto`, `manual` and `dontAsk`; add one deliberately if a team needs it.
- A repo path is checked for `.git` when it is added, not when the registry loads, so one moved repo doesn't stop the fleet server from starting.
- Gotcha: `bash` on PATH is WSL (`C:\WINDOWS\system32\bash.exe`). Git Bash is at `C:\cmdr\vendor\git-for-windows\bin\bash.exe` (git comes from cmder). `fleet.doctor` checks this.
- Gotcha: uv fails TLS to PyPI on this machine ("invalid peer certificate: UnknownIssuer"). Set `UV_SYSTEM_CERTS=1` or pass `--system-certs`.
- Gotcha: `claude --help` (2.1.289) doesn't list `--max-turns`. Verify it before Phase 2 relies on it for per-job budgets.
- The fleet server uses the `mcp` Python SDK 2.x. In 2.x, `FastMCP` is `MCPServer` (`mcp.server.mcpserver`). A tool must raise `ToolError` for a message the PM should see; any other exception reaches the PM only as "Error executing tool <name>". Tests use `Client(server)` in-process and `Client(StdioServerParameters(...))` for a real subprocess.
- `.mcp.json` launches the server with `uv run --quiet --directory C:/src/AIPM python -m fleet.server` and sets `UV_SYSTEM_CERTS=1`. The server re-reads `projects.yaml` and `sessions.json` on every call, because other tools write them. `AIPM_REGISTRY` and `AIPM_SESSIONS` point it at other files for tests.
- A headless `claude -p` call that just replies "ok" reports about 50k tokens, mostly cached system prompt and tools. Every team dispatch starts from that baseline; size `max_tokens_per_job` with it in mind.
- Gotcha: from Windows, git refuses `C:\src\AIPM` with "dubious ownership" because the folder is owned by `BUILTIN\Administrators` (created from WSL). Workaround: `git -c safe.directory=C:/src/AIPM ...`, or add it once with `git config --global --add safe.directory C:/src/AIPM`.
