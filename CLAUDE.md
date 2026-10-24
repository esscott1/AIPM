# AIPM repo — build rules

This repo builds AIPM, a program-manager agent over my other Claude Code repos. Read `docs/architecture.md` and `docs/roadmap.md` before starting work.

## Current phase

Phase 1 (scaffold). Work only on unchecked items in `docs/roadmap.md` under Phase 1 unless told otherwise. Tick items off in the roadmap as they are done.

## Working rules

- Work on a feature branch; never commit directly to `main`. I merge PRs.
- Keep `docs/architecture.md` true: if a design decision changes, update it in the same PR.
- Record decisions and gotchas in `memory.md`.
- The fleet server must never read, store or forward Claude or GitHub credentials. Teams run through the unmodified `claude` CLI signed in with my own account.
- Never use `bypassPermissions`.
- Secrets and runtime state stay out of git: `fleet/sessions.json`, `fleet/jobs/`, `.env`.

## Later (Phase 1 deliverable)

When the PM role is ready, this file gains the PM instructions: dispatch through fleet tools, approve or reject PR requests, escalate merges to `main` and repo creation to me, and never edit project code directly.
