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
- Work happens on branch `claude/codebase-review-setup-rz93qm`.
