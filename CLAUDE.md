# CLAUDE.md — Working guidance for ThesisTrace

Read `HANDOFF.md` first for project state and next steps.

## Lawrence's standing preferences (honor every session)

1. **Mark the recommended option.** Whenever presenting choices, clearly highlight which one is recommended (and why), for quality development.
2. **Commit frequently** — and always commit at the end of every major task, with a clear message.
3. **Explain in plain language.** After each major task, give an easy-to-read recap of what was done and how to review it, so Lawrence can step away and come back without digging.

## Project shape

- BMad planning-driven project. Planning artifacts live under `_bmad-output/`.
- Canonical contract: `_bmad-output/specs/spec-thesistrace/SPEC.md` (+ its adopted companions: the architecture spine, the PRD, and `foundational-decisions.md`).
- Deterministic/LLM boundary is inviolable: all scores/numbers are computed deterministically; the LLM only explains and cites, never originates a figure.

## Git workflow (read before making any commit)

Lawrence runs multiple sessions on this repo (desktop and cloud, sometimes overlapping) — a prior collision between two concurrent sessions caused a real divergence (see `HANDOFF.md`'s "Real bug found and fixed post-implementation" section for the full story). To prevent a repeat:

1. **Every session works on its own new feature branch — never push directly to `main`.** At the start of a session, `git pull origin main` first, then create a fresh branch (e.g. `claude/<short-task-description>-<date>`). Never reuse an old branch name from a prior session.
2. **Merge back via PR, not a direct push to `main`.** This surfaces any conflict with other concurrent work as a normal PR diff to review, instead of a rejected push discovered after a lot of independent work has piled up.
3. **Pull `main` before starting substantive planning/architecture work specifically** — BMad workflow state (memlogs, spines, specs) can diverge just as easily as source code, and is harder to merge automatically.
4. Push and open the PR at natural checkpoints (end of a story/epic, end of a planning phase) rather than batching a very long uninterrupted run — smaller, more frequent syncs make any real conflict small and easy to see.
