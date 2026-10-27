# AIPM Roadmap

Seven phases. Each ends with a test that proves it works before the next starts. See [architecture.md](architecture.md) for the design.

| Phase | Theme | Done when |
| --- | --- | --- |
| 0 | Repo and docs | This repo exists on GitHub with the architecture and roadmap |
| 1 | Scaffold | MonteCarlo is adopted with `/adopt-project`, and the PM sends it a task and gets a report back |
| 2 | Parallel | One ask runs in all three repos at once |
| 3 | Bootstrap | otsconsulting exists on GitHub with a working team |
| 4 | Visibility | One command, or the control panel, shows status across all repos and approves a PR |
| 5 | Schedule | The board is current each morning |
| 6 | Review and evaluation | One architecture review runs both ways, independently, and the two assessments are compared |
| 7 | Enterprise architecture | The enterprise architect answers one portfolio question in writing, with its cost of change and my decision |

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
- [ ] `evals/` with the two tiers documented in `evals/README.md`, and fixture repos under `evals/fixtures/`. Evals land with the feature they test, never in a phase of their own (see [architecture.md](architecture.md), Evaluating AIPM itself)
- [ ] Tier 1 evals against `fake_claude`: brief assembly per framework, report-schema enforcement, paused dispatch queues, one job per project, mode ceiling
- [ ] Tier 2 eval — brief compliance: a real team works on a feature branch, opens no PR, returns a valid report. Runs with the live check below; ask first
- [ ] Tier 2 eval — PM role: given a task it could do by editing a project repo itself, the PM dispatches instead and leaves the repo untouched
- [ ] Tier 2 eval — reconcile briefing: after commits made outside AIPM, the team's next task shows it knows what changed
- [x] `projects.yaml` schema: path, remote, goal, model, permission_mode, budget (token cap, default 100K and report-only; optional turn limit), status. Local and written by fleet tools; `session_id` and `last_seen_commit` live in `sessions.json`
- [x] `fleet/server.py`: MCP server exposing `list_projects`, `project_status`, `dispatch`, `get_report`; `dispatch` runs jobs in the background
- [x] Teams run through the unmodified `claude` CLI headless (`-p --resume --output-format json`), `cwd` = repo, on the claude.ai sign-in (API key variables removed)
- [ ] `sessions.json` persistence (`session_id`, `last_seen_commit`); resume always from the registered path (`session_id` done; `last_seen_commit` comes with `reconcile`)
- [x] Structured end-of-task report (summary, branch, changed, tests, blockers, next step, tokens used)
- [ ] `reconcile(project)`: fetch, diff since `last_seen_commit`, detect merged PRs via `gh`, brief the team; runs before every dispatch
- [ ] `pause` / `resume`; a dispatch to a paused project is refused with a reminder and saved to `fleet/queue.json`; `resume` lists the queued tasks to dispatch or discard
- [ ] `projects.yaml` gains `framework` (spec-kit | gsd | openspec | none), `context_docs`, `northstar`, and a top-level `portfolio_path`. The model sets `extra="forbid"`, so these are rejected until added; they stay inert until Phases 6–7, but land now so the schema doesn't need migrating later
- [ ] The dispatch brief names the project's `framework` and tells the team to enter through it; `none` means its `CLAUDE.md` alone
- [ ] `/adopt-project` skill (find, inspect, pick context docs, name the north star, detect the framework, register, health check; the team always starts in a fresh session) and `/retire-project`. Adoption changes nothing in the repo
- [ ] Fresh-start orientation: a team's first task in a new session begins by reading the project's `context_docs`
- [x] `.mcp.json` registers the fleet server with the PM session
- [ ] Live check of `dispatch`: real `claude -p` runs against a throwaway repo (deferred until later in Phase 1; ask first, about 50k tokens per run)
- [ ] **Exit test:** adopt MonteCarlo, dispatch "report your current state", receive the report in the PM session

## Phase 2 — Parallel

- [ ] `job_status` and `cancel` for the background jobs `dispatch` starts
- [ ] `broadcast(instruction, projects)`
- [ ] Job stops and reports if its branch or worktree changed underneath it
- [ ] Decide whether the token cap ever stops a job (report-only in Phase 1); tokens reported per job and repo
- [ ] Adopt job-search-assistant
- [ ] **Exit test:** one broadcast ("report dependency status") runs in all adopted repos concurrently

## Phase 3 — Bootstrap and PR flow

- [ ] `templates/CLAUDE.md.tmpl`, `templates/memory.md.tmpl`, `templates/agents/` (spike, planner, researcher)
- [ ] `create_project` with an approval stop before `gh repo create`
- [ ] `create_project` applies the "Protect main" ruleset (PR required, no force push, no deletion, no bypass) to every new repo
- [ ] Apply the same ruleset to an adopted repo that lacks it, only when I ask (adoption itself never changes a repo)
- [ ] `request_pr` / `approve_pr` / `reject_pr`; teams cannot open a PR without approval
- [ ] `notify_merged` triggers team cleanup (delete merged branch and worktree) per the team's CLAUDE.md
- [ ] Tier 2 eval — PR approval judgment: given a report that doesn't match its task, the PM rejects it with a reason naming the mismatch
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

## Phase 6 — Review and evaluation

Goal: AIPM can assess an adopted project two ways, independently, and compare the answers.

- [ ] `inspect_project(project)`: AIPM reads a repo read-only (tree, context docs, framework artifacts, recent history) without dispatching to its team
- [ ] `review(project, kind)` dispatched to the team, where kind is `architecture`, `consistency` or `northstar`
- [ ] AIPM's own assessment of the same kinds, from `inspect_project`, written to `portfolio/assessments/<project>/` with its model and the commit it was made against
- [ ] **Independence rule enforced:** `get_report` on a review job withholds the team's report until AIPM's own assessment for that review is recorded, and the review runs on a different model than the team's
- [ ] Comparison output: where the two agree, where they disagree
- [ ] `northstar_review(project)`: read the project's north star, report drift against recent work, propose an update as a task for the team
- [ ] `eval_create(project, target)` and `eval_run(project)`, in whatever format the repo already uses; a repo with none gets a format proposed first
- [ ] Eval runs get their own budget class, separate from the per-job token cap
- [ ] AIPM's own subagents in `.claude/agents/`: `architecture-reviewer`, `eval-author`
- [ ] Tier 1 eval: `get_report` on a review job withholds the team's report until AIPM's assessment is recorded
- [ ] Tier 2 eval — review recall: what share of the defects planted in a fixture repo an architecture review finds
- [ ] Tier 2 eval — independence in substance: the two assessments differ rather than converging trivially
- [ ] **Exit test:** an architecture review of MonteCarlo runs both ways, the team's report stays withheld until AIPM's assessment is recorded, and the comparison names at least one point of disagreement

## Phase 7 — Enterprise architecture

Goal: AIPM reasons about the portfolio, not just the projects in it.

- [ ] `portfolio/` tree with `northstar.md`, `reviews/`, `assessments/`, `evals/` and `decisions.md`; `portfolio_path` relocates it
- [ ] `enterprise-architect` subagent in AIPM's own `.claude/agents/`
- [ ] `ea_review(question)`: a portfolio-level assessment across every adopted repo, written to `portfolio/reviews/`
- [ ] Every recommendation records what adopting it would cost and what is given up either way
- [ ] A declined recommendation is recorded in `portfolio/decisions.md` with my reason, so it isn't raised again from scratch
- [ ] Portfolio north star: set it, and roll each project's north star up against it
- [ ] An accepted recommendation becomes tasks dispatched to the affected teams, under the usual gates
- [ ] Tier 2 eval — enterprise architect: an issue planted across two fixture repos is surfaced as a portfolio question
- [ ] **Exit test:** the enterprise architect answers one portfolio question (for example where eval sets should live) with a recommendation, its cost of change, and my accept-or-decline recorded
