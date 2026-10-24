# AIPM Roadmap

Five phases. Each ends with a test that proves it works before the next starts. See [architecture.md](architecture.md) for the design.

| Phase | Theme | Done when |
| --- | --- | --- |
| 0 | Repo and docs | This repo exists on GitHub with the architecture and roadmap |
| 1 | Scaffold | MonteCarlo is adopted with `/adopt-project`, and the PM sends it a task and gets a report back |
| 2 | Parallel | One ask runs in all three repos at once |
| 3 | Bootstrap | otsconsulting exists on GitHub with a working team |
| 4 | Visibility | One command, or the control panel, shows status across all repos and approves a PR |
| 5 | Schedule | The board is current each morning |

## Phase 0 — Repo and docs

- [x] Architecture document (`docs/architecture.md`)
- [x] Phased roadmap (`docs/roadmap.md`)
- [x] Design dashboard (`dashboard/aipm-board.html`)
- [x] `git init`, first commit, push to `esscott1/AIPM`
- [x] "Protect main" ruleset active on `esscott1/AIPM`

## Phase 1 — Scaffold

Goal: one PM session can drive one adopted team end to end.

- [x] Decide where the fleet server runs: native Windows
- [x] Windows prerequisites: Python 3.12+, Git for Windows (Git Bash), `claude` and `gh` signed in on Windows (`uv run python -m fleet.doctor`)
- [ ] `CLAUDE.md` gains the PM role, approval gates and "never edit project code" rule
- [x] `projects.yaml` schema: path, remote, goal, model, permission_mode, budget (turns, tokens), status. Local and written by fleet tools; `session_id` and `last_seen_commit` live in `sessions.json`
- [ ] `fleet/server.py`: MCP server exposing `list_projects`, `project_status`, `dispatch`, `get_report`
- [ ] Teams run through the unmodified `claude` CLI headless (`-p --resume --output-format json`), `cwd` = repo
- [ ] `sessions.json` persistence (`session_id`, `last_seen_commit`); resume always from the registered path
- [ ] Structured end-of-task report (changed, tests, blockers, next step, tokens used)
- [ ] `reconcile(project)`: fetch, diff since `last_seen_commit`, detect merged PRs via `gh`, brief the team; runs before every dispatch
- [ ] `pause` / `resume`; dispatches to a paused project wait
- [ ] `/adopt-project` skill (find, inspect, team rules, import session, seed subagents, register, health check) and `/retire-project`
- [ ] `.mcp.json` registers the fleet server with the PM session
- [ ] **Exit test:** adopt MonteCarlo, dispatch "report your current state", receive the report in the PM session

## Phase 2 — Parallel

- [ ] Background jobs with `job_status` and `cancel`
- [ ] `broadcast(instruction, projects)`
- [ ] Job stops and reports if its branch or worktree changed underneath it
- [ ] Token budgets enforced per job (`max_turns`, `max_tokens_per_job`), tokens reported per job and repo
- [ ] Adopt job-search-assistant
- [ ] **Exit test:** one broadcast ("report dependency status") runs in all adopted repos concurrently

## Phase 3 — Bootstrap and PR flow

- [ ] `templates/CLAUDE.md.tmpl`, `templates/memory.md.tmpl`, `templates/agents/` (spike, planner, researcher)
- [ ] `create_project` with an approval stop before `gh repo create`
- [ ] `create_project` applies the "Protect main" ruleset (PR required, no force push, no deletion, no bypass) to every new repo
- [ ] `/adopt-project` offers to apply the same ruleset to adopted repos that lack it
- [ ] `request_pr` / `approve_pr` / `reject_pr`; teams cannot open a PR without approval
- [ ] `notify_merged` triggers team cleanup (delete merged branch and worktree) per the team's CLAUDE.md
- [ ] **Exit test:** create otsconsulting, staff its team, run its kickoff task, open and merge its first PR, team cleans up

## Phase 4 — Visibility and interfaces

- [ ] `/standup` and `STATUS.md` roll-up (git log, open PRs, last report, tokens per repo)
- [ ] AIPM Control Panel artifact in the Claude desktop app: status board, PR queue with Approve/Reject, dispatch and broadcast, merge notices
- [ ] Snapshot saved to the artifact database for read-only viewing on other devices
- [ ] Optional Jira sync
- [ ] **Exit test:** approve a PR from the control panel and see it reflected in `STATUS.md`

## Phase 5 — Schedule

- [ ] Nightly scheduled task: `reconcile` all projects, then `standup`
- [ ] **Exit test:** the board is current each morning without manual action
