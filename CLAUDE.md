# CLAUDE.md — Working guidance for ThesisTrace

Run `/session-start` first thing every session — it reads `.claude/handoff/CURRENT.md`
(the single source of truth for resume state) and `.claude/context/project-context.md`
(durable rules/learnings, loaded every session). Run `/session-end` before closing a
window. See `claude-workflow-kit` conventions below.

## Context Management (CRITICAL)

The agent manages its own context budget. These rules constrain **autonomous**
file reading — the user can always ask for any file explicitly.

### Core rule: just-in-time loading
Load a file ONLY when the current task actually needs it. Don't pre-read "to be safe."
Existence and size can be checked without spending tokens (see below).

### Required at session start
- `.claude/handoff/CURRENT.md` — session continuity (run `/session-start`).
- `.claude/context/project-context.md` — durable rules/learnings.

### Never auto-read (unless actively working on it, or the user asks)
- ❌ Large planning docs / specs under `_bmad-output/` — grep for the specific section instead of reading the whole file.
- ❌ `_bmad-output/archive/HANDOFF-*.md` — historical narrative, superseded by `project-context.md` + git/PR history.
- ❌ Slash-command / skill definition files (`.claude/commands/*`, `.claude/skills/*`) — read only when actively invoking or editing one.
- ❌ Config files (`package.json`, `pyproject.toml`, …) unless modifying them.
- ❌ Code files not being actively changed.

### Context budget targets
- **Session start:** < 25,000 tokens (~10% of budget).
- **Red flag:** > 50,000 tokens loaded before real work begins.

### Verify without reading
```bash
test -f file && echo EXISTS || echo MISSING   # existence, 0 tokens
wc -l file                                     # size, 0 content tokens
grep -n "pattern" bigdoc.md                    # locate a section before reading it
```

## Lawrence's standing preferences (honor every session)

1. **Mark the recommended option.** Whenever presenting choices, clearly highlight which one is recommended (and why), for quality development.
2. **Commit frequently** — and always commit at the end of every major task, with a clear message.
3. **Explain in plain language.** After each major task, give an easy-to-read recap of what was done and how to review it, so Lawrence can step away and come back without digging.
4. **Ask for all permissions in one go.** Before starting research or any multi-fetch task, list every web domain, live API fetch, or approval the whole task will need and ask **once**. Never drip-feed one approval at a time — it turns a single task into a chain of interruptions for no added safety, since the activity itself is already approved. Applies equally to the standing "ask before live EDGAR fetch" rule: name all the tickers/CIKs in a single request.

## Project shape

- BMad planning-driven project. Planning artifacts live under `_bmad-output/`.
- Canonical contract: `_bmad-output/specs/spec-thesistrace/SPEC.md` (+ its adopted companions: the architecture spine, the PRD, and `foundational-decisions.md`).
- Deterministic/LLM boundary is inviolable: all scores/numbers are computed deterministically; the LLM only explains and cites, never originates a figure.

## Git workflow (read before making any commit)

Lawrence runs multiple sessions on this repo (desktop and cloud, sometimes overlapping) — a prior collision between two concurrent sessions caused a real divergence (see `_bmad-output/archive/HANDOFF-2026-07-29.md`'s "Real bug found and fixed post-implementation" section for the full story). To prevent a repeat:

1. **Every session works on its own new feature branch — never push directly to `main`.** At the start of a session, `git pull origin main` first, then create a fresh branch (e.g. `claude/<short-task-description>-<date>`). Never reuse an old branch name from a prior session.
2. **Merge back via PR, not a direct push to `main`.** This surfaces any conflict with other concurrent work as a normal PR diff to review, instead of a rejected push discovered after a lot of independent work has piled up.
3. **Pull `main` before starting substantive planning/architecture work specifically** — BMad workflow state (memlogs, spines, specs) can diverge just as easily as source code, and is harder to merge automatically.
4. Push and open the PR at natural checkpoints (end of a story/epic, end of a planning phase) rather than batching a very long uninterrupted run — smaller, more frequent syncs make any real conflict small and easy to see.
