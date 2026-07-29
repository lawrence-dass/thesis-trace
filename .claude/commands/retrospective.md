---
description: 'Capture learnings after an epic/milestone and feed them into project-context.md.'
argument-hint: 'Optional: the epic/milestone name that just completed'
---

# Retrospective — Capture & Persist Learnings

Run after an epic, milestone, or phase completes. The goal is to turn what the last
stretch of work taught you into durable rules future sessions load automatically —
so the same lesson isn't re-learned the hard way.

Complements `/session-end` (per-session) and `optimize-context` (file hygiene).
This one is about **durable learnings**, not session state.

---

## Steps

### 1. Gather what happened
Look at the completed work:
```bash
git log --oneline {since-last-retro-or-tag}..HEAD
```
Skim the stories/tasks completed and any recent `.claude/handoff/archive/` entries.

### 2. Reflect — surface the learnings
Ask (and answer from the evidence):
- **What went well** that we should keep doing?
- **What was painful or slow** — and what would prevent it next time?
- **What surprised us** — a gotcha, a non-obvious constraint, a wrong assumption?
- **What decisions** did we make that future work must respect?

Keep only learnings that are **durable and cross-task** — things that will still be
true next epic. Session-specific noise does not belong here.

### 3. Draft additions to project-context.md
For each durable learning, draft a concise entry under a dated heading:
```markdown
## Learnings — {YYYY-MM-DD} ({epic/milestone})
- {learning, stated as a rule or constraint}. [Source: {path or PR/commit}]
```
Prefer rules over stories: "Always X because Y" beats "we had a bug where…".
Cite a source where one exists.

### 4. Confirm and write
Show the draft. On approval, append it to `.claude/context/project-context.md`.

> If `project-context.md` is getting long (> ~200 lines), suggest running
> `optimize-context` to consolidate before it bloats the always-loaded budget.

### 5. Confirm complete
```
✅ Retrospective captured
   {N} learnings → .claude/context/project-context.md
   {if suggested} Consider running optimize-context — project-context.md is at {n} lines.
```

---

## Notes
- Retrospective output is **rules for the future**, not a status report.
- Be honest about what went wrong — the value is in preventing the repeat.
