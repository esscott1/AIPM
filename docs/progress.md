# AIPM progress and open tasks

As of 2026-10-25. Read this, then [architecture.md](architecture.md) and [roadmap.md](roadmap.md), before picking up a task. The roadmap is the source of truth for scope. This file says where the work stands, how it is being done, and which tasks are open.

## Where things stand

- **Phase 0 (repo and docs):** done.
- **Phase 1 (scaffold):** in progress. Done:
  - the fleet server with `list_projects`, `project_status`, `dispatch` and `get_report`;
  - the `projects.yaml` registry;
  - headless `claude -p` runs;
  - the structured report;
  - `.mcp.json`;
  - the Windows prerequisites doctor.
- **Phases 2–5:** not started.
- **Last merged PR:** #8, on 2026-10-25. It settled three decisions:
  - Adopting a repo only registers it and never changes it.
  - Every new team starts in a fresh session and reads the project's context docs.
  - A dispatch to a paused project is refused and queued.
- **In progress:** adopting GitHub Spec Kit to build the rest of Phase 1, on branch `feat/adopt-spec-kit` (PR A below). This file was added on that branch.

## How the remaining Phase 1 work is being built

The rest of Phase 1 is built with [Spec Kit](https://github.com/github/spec-kit) 1.2.3. Each remaining roadmap item becomes one Spec Kit feature, on its own `feat/<item>` branch and pull request.

**The owner is learning Spec Kit, so they start every step themselves.**
- The skills are installed with `disable-model-invocation: true`, so an agent cannot start them.
- **Before each step, give the owner a short note:**
  - what the step does, and the Spec Kit idea it teaches;
  - what files it writes;
  - what to review;
  - the exact command to type.
- **After each step:**
  - summarize what it produced;
  - flag any conflict with `architecture.md` or `roadmap.md`;
  - list the decisions the owner needs to make;
  - wait for the owner's OK before the next step.

**The cycle for each feature:**
1. `/speckit-specify`: what and why, no technology. It must name the roadmap item and the architecture sections it implements.
2. `/speckit-clarify`: the owner answers questions about gaps.
3. `/speckit-plan`: how, including contracts for MCP tool inputs and outputs and for file formats. Fixed constraints, every time:
   - Python 3.12+ on Windows;
   - teams run as `claude -p` subprocesses;
   - no Agent SDK library;
   - no API key;
   - no stored credentials.
4. `/speckit-tasks`: an ordered, testable task list.
5. `/speckit-analyze`: fix every mismatch before coding.
6. `/speckit-implement`, then `/speckit-converge`. Repeat both until converge adds nothing.
7. Open the PR. It carries:
   - the spec folder;
   - the code and tests;
   - the roadmap tick;
   - any `architecture.md` update.

   The owner merges.

Doc-only changes and small fixes skip Spec Kit.

## Open tasks

Do them in order. Each needs the one before it merged.

| # | Task | Branch | Status | Needs the owner |
| --- | --- | --- | --- | --- |
| A | Adopt Spec Kit (no code changes) | `feat/adopt-spec-kit` | In progress: init done, constitution next | Yes, at every Spec Kit step, and to merge |
| 1 | `reconcile` (diffs since the `last_seen_commit` adoption wrote) | `feat/reconcile` | Not started | Spec Kit steps, merge |
| 2 | `pause` / `resume` and the queue | `feat/pause-resume` | Not started | Spec Kit steps, merge |
| 3 | `/adopt-project`, `/retire-project`, `context_docs`, fresh-start orientation, `last_seen_commit` written at adoption | `feat/adopt-project` | Not started | Spec Kit steps, merge |
| 4 | PM role in `CLAUDE.md` (doc-only, no Spec Kit) | `docs/pm-role` | Not started | Merge |
| 5 | Live check of `dispatch`: real `claude -p` runs against a throwaway repo, about 50k tokens per run | none | Not started | **Must approve before any run** |
| 6 | Phase 1 exit test: adopt MonteCarlo, dispatch "report your current state", receive the report | none | Not started | Yes |

### A. Adopt Spec Kit

1. [x] Install `specify-cli` 1.2.3 as a uv tool.
2. [x] `specify init --here --force --integration claude --script py --integration-options="--no-model-invocation" --non-interactive`. Commit `e6bac26`:
   - adds `.specify/` and 10 `.claude/skills/speckit-*` skills;
   - adds `.claude/settings.local.json` to `.gitignore`;
   - changes no other tracked file;
   - the PowerShell scripts that came along are unused, since `.specify/integration.json` says `script: py`.
3. [ ] **Next: the constitution.** The owner runs `/speckit-constitution` with the text below, and the agent reviews the result.
   - Every principle must trace to `CLAUDE.md`, `architecture.md` or `roadmap.md`.
   - Remove any generic template principle the project never adopted, such as test-first or library-first.
4. [ ] Add a short "Building with Spec Kit" section to `CLAUDE.md`, leaving the rest unchanged:
   - one roadmap item per Spec Kit feature, on a `feat/<item>` branch;
   - the PR carries the spec, code, tests, roadmap tick and any `architecture.md` update;
   - small fixes and doc-only changes skip Spec Kit.
5. [ ] `roadmap.md`: add a ticked Phase 1 item, "Build with Spec Kit (constitution, one spec per item)".
6. [ ] `memory.md`: add why AIPM uses Spec Kit, the init choices in step 2, and the environment notes below.
7. [ ] Run `uv run pytest`. It should pass unchanged.
8. [ ] Push, open the PR. The owner merges, then says "clean up".

**The text for step 3:**
```
/speckit-constitution Write AIPM's constitution only from rules that already hold. First read CLAUDE.md, all of docs/architecture.md and all of docs/roadmap.md. Principles: (1) Architecture and roadmap first: every spec and plan reads docs/architecture.md and docs/roadmap.md, names the architecture sections and the roadmap item it implements, and builds only what the roadmap's current phase holds. (2) Plans stay true: a feature that changes the design updates docs/architecture.md in the same PR, a feature that finishes a roadmap item ticks it in docs/roadmap.md, and a conflict with either doc is a mismatch to fix before coding. (3) Every change reaches main only through a pull request from a feature branch; the user merges. (4) The fleet server never reads, stores or forwards Claude or GitHub credentials; bypassPermissions is never used; secrets and runtime state (projects.yaml, fleet/sessions.json, fleet/jobs/, fleet/queue.json, .env) stay out of git. (5) Teams run through the unmodified claude CLI on Windows on the user's claude.ai sign-in; the fleet server is Python 3.12+; no Agent SDK library; no API key unless the user confirms twice. (6) Adopting a repo registers it and never changes it. Adoption writes last_seen_commit as the default branch's current commit. The default branch is whatever git reports (main, master, or another name); do not assume the name. job-search-assistant is its own repo, not inside ClaudeCowork. Precedence: if this constitution disagrees with CLAUDE.md, docs/architecture.md or docs/roadmap.md, those win and the constitution is corrected. Add no principle that isn't already true.
```

### Notes for tasks 1–3

- **Task 1, `reconcile`:**
  - Read each repo's default branch from git. Do not assume the name. MonteCarlo's is `master`; another repo's may be `main` or something else.
  - Change the team brief in `fleet/runner.py` from "never on main" to "never on the default branch".
  - Put the reconcile brief in the dispatch prompt, so it costs no extra run.
  - Diff since `last_seen_commit` when it is set. Reconcile does not create that field. Adoption (task 3) writes it. Until then, a missing value means there is nothing to brief; tests may set the field directly.
- **Task 2, `pause` / `resume`:**
  - A refused dispatch is saved to `fleet/queue.json`, which needs adding to `.gitignore`.
  - `resume` lists the queue. The owner picks which tasks to dispatch or discard, and queued tasks never run on their own.
- **Task 3, adoption:** it never writes to the adopted repo, so MonteCarlo's `openspec/` folder and OpenSpec skills are left alone automatically. The spec should still name that as a requirement. Adoption writes `last_seen_commit` in `sessions.json` as the default branch's current commit, and no session. `create_project` does the same when it registers a new repo.
- **After task 1:** decide with the owner whether each `specs/<feature>/` folder is a frozen record or a living contract. Record the answer in `CLAUDE.md`.
- **Code to reuse:**
  - `read_git_state` and `_git` in `fleet/server.py`;
  - `SessionState` and `record_session_id` in `fleet/sessions.py`;
  - `Registry.set_status`, `add` and `remove` in `fleet/registry.py`;
  - `JobStore.running` in `fleet/jobs.py`;
  - `build_prompt` and `TEAM_BRIEF` in `fleet/runner.py`;
  - `write_atomic` in `fleet/files.py`.
- **Tests:** use `tests/fake_claude.py` and the `Fleet` fixture in `tests/test_dispatch.py`, so tests cost no tokens.

## Rules any agent must follow

These come from `CLAUDE.md`; read it in full.
- Work on a feature branch and reach `main` only through a PR. Never commit to `main`.
- Never merge, approve or close a PR. The owner does.
- Keep `architecture.md` true in the same PR as any design change. Record decisions and gotchas in `memory.md`.
- Never run a team on an API key, use `bypassPermissions`, or read, store or forward credentials.
- No prices or dollar costs in commits, PRs or files. Report tokens, pass rates and durations instead.
- Keep secrets and runtime state out of git.
- Ask before any real `claude -p` run.

## Environment notes (Windows host)

- **Norton intercepts HTTPS.** Norton's Web Shield re-signs pypi.org, files.pythonhosted.org and github.com with "Norton Web/Mail Shield Root", which uv doesn't trust. Prefix uv commands that download with `UV_SYSTEM_CERTS=1`.
- **Norton flagged `specify.exe`.** Norton Auto-Protect flagged the uv launcher as `IDP.Generic`, a false positive.
  - It is now excluded at `%USERPROFILE%\.local\bin\specify.exe` and `%USERPROFILE%\AppData\Roaming\uv\tools\specify-cli\Scripts\specify.exe`. A Windows restart was needed before Norton let the file be created again.
  - `uv tool upgrade specify-cli` recreates the launcher. Before upgrading, check that the PyPI release came from `github/spec-kit`'s "Publish to PyPI" workflow.
- **Two bashes.** `bash` on PATH is WSL. Git Bash lives under the cmder install; `fleet.doctor` checks this.
- **Git ownership.** If Windows git reports "dubious ownership" for `C:\src\AIPM`, run `git config --global --add safe.directory C:/src/AIPM`.
- **Spec Kit commands** are spelled `/speckit-<step>`, with a hyphen.
