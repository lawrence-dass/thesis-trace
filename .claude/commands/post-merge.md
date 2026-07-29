---
description: 'After a PR merges to main, sync and set up the next unit of work.'
argument-hint: 'Optional: the story/task id that was merged'
---

# Post-Merge Workflow

**Purpose:** When a PR merges to `main`, automatically sync local state and set up
the next unit of work on a fresh branch — so there is zero "where was I?" friction.

This is the BMAD-free, generic version. It reads the next task from a simple
backlog/status file instead of a sprint-status tool. Adapt the file paths to your
project's tracking convention.

---

## Trigger Recognition

Run when the user signals a merge:
- "PR merged", "Story X.Y merged to main", "branch merged"
- A pasted GitHub merge confirmation

---

## Steps

### 1. Acknowledge
Identify which task/story was merged (from the argument or context). Display:
> "Story X.Y merged to main. Running post-merge sync…"

### 2. Sync main
```bash
git checkout main
git pull origin main
git log -1 --oneline
```

### 3. Pick the next task
Read the project's backlog/status file (whichever the project uses), for example:
- `.claude/handoff/STATUS.md`, a `BACKLOG.md`, a `TODO.md`, or a GitHub issues list.

Select the **first** item with status `ready` / `todo` / `backlog` (in file order).
Extract its id and short title. If none remain, stop and report:
> "No pending tasks found — backlog is clear. Consider a retrospective."

### 4. Propose and confirm
Show the user:
- The next task id + title
- The branch name that will be created (see convention below)
- Ask: **"Proceed?"**

Only continue on explicit confirmation (yes / y / go / proceed). On no → HALT.

### 5. Create the branch
```bash
git checkout -b feature/{short-branch-name}
```
Then update the status file to mark the task `in-progress`, and (optionally)
scaffold a task file from the project's story/task template.

### 6. Confirm completion
```
✅ Synced main ({latest commit})
✅ Created branch: feature/{short-branch-name}
✅ Next task: {id} — {title}  (marked in-progress)

Next: review the task, then start implementation.
```

---

## Branch Naming Convention

From a task key like `1-2-configure-database-schema`:
- Keep the epic-story numbers: `1-2`
- Take the first 3–4 meaningful words of the title
- Drop filler words: "with", "and", "the", "for", "a"
- Result: `feature/1-2-config-db-schema`

Examples:
- `1-1-initialize-project-with-core-deps` → `feature/1-1-init-project`
- `2-1-implement-anonymous-auth`         → `feature/2-1-anon-auth`

---

## Error Handling

| Situation | Action |
|-----------|--------|
| No pending tasks | Stop. Suggest a retrospective or new planning. |
| `git pull` fails / conflict | Report it. Ask the user to resolve manually. |
| Branch already exists | Ask whether to reuse, delete, or rename. |
| User declines at step 4 | Stop. Do not create a branch. |
| Status file missing | Ask the user which task is next, or run planning first. |

---

## Notes

- This never force-pushes and never merges — it only syncs `main` and branches off it.
- Keep the confirmation gate at step 4. Branch creation should always be intentional.
