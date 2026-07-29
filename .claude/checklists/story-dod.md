# Definition of Done — Story Completion Checklist

**Validation target:** the story/task file · **Criticality:** HIGHEST

A story is "ready for review" **only when every item below is satisfied.** Run this
at the end of `/implement-story` (and again during `/run-qa`). Adapt items to your
project — but don't quietly drop the quality bar.

> Read `.claude/context/project-context.md` for the project's test/coverage/lint
> commands and NON-NEGOTIABLE domain rules; judge against those.

## Context & Requirements
- [ ] **Acceptance criteria satisfied** — implementation meets EVERY acceptance criterion in the story.
- [ ] **Architecture compliance** — follows the patterns/constraints in the story's Dev Notes and `project-context.md`.
- [ ] **Dependencies within scope** — only uses dependencies named in the story or `project-context.md`.
- [ ] **Previous learnings applied** — relevant learnings from `project-context.md` were honored.

## Implementation
- [ ] **All tasks complete** — every task and subtask marked `[x]`.
- [ ] **Edge cases handled** — error conditions and boundaries addressed.
- [ ] **No orphan code** — nothing implemented that isn't mapped to a task/AC.

## Testing & Quality
- [ ] **Tests added/updated** for all new or changed functionality.
- [ ] **Coverage meets target** (default ≥ 80% for new code).
- [ ] **All existing tests pass** — no regressions.
- [ ] **Lint & type checks pass** where configured.
- [ ] **Tests are real** — they actually exist and pass; no faked or skipped-without-reason tests.

## Documentation & Tracking
- [ ] **File List complete** — every new/modified/deleted file listed (paths from repo root).
- [ ] **Dev Agent Record updated** — implementation notes / debug log for this work.
- [ ] **Change summary** — a clear note of what changed and why.
- [ ] **Section discipline respected** — only permitted sections of the story file were edited
      (Tasks checkboxes · Dev Agent Record · File List · Status). Acceptance criteria untouched.

## Final Status
- [ ] **Status set to `review`** in the story/status file.
- [ ] **No HALT conditions** — no blocking issues or incomplete work remaining.
- [ ] **Summary ready** for the user / reviewer.

## Output
```
Definition of Done: {PASS | FAIL}

Story: {story-id}
Score: {completed}/{total} items passed
Tests: {summary}
```
**If FAIL** — list each failed item and the action needed before the story can be marked ready.
**If PASS** — the story is ready for `/review-code`.
