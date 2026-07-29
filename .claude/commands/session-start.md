---
description: 'Resume work from the last session. Run at the start of any new window.'
argument-hint: 'Optional: "fresh" to skip the handover and orient from git + status instead'
---

# Session Start — Resume Instructions

Load the previous session state and orient for continuation in a fresh window.
This is orientation ONLY — do not begin implementation and do not edit files.

If the user passed `fresh` as an argument, skip Step 1–3 and go straight to Step 4 (fresh orientation).

---

## Step 1: Load the Handover

Read `.claude/handoff/CURRENT.md`.

**If the file does not exist:**
- Output: "No previous handover found."
- Skip to Step 4 (fresh orientation mode).

Parse the timestamp from the header: `# Handover — {YYYY-MM-DD HH:MM}`.

**Staleness check:**
- Under 24 hours → proceed normally.
- 24 hours – 7 days → prepend `⚠️ Handover is {X} hours old — verify the git state below still matches.`
- Over 7 days → prepend `⚠️ Handover is {X} days old — treat with caution; re-orient from git if it looks wrong.`

Check `.claude/handoff/archive/` for timestamped copies. If any copy is **newer** than `CURRENT.md`, warn and use the newer file as the source of truth.

---

## Step 2: Verify Git State

Run:
```bash
git branch --show-current
git status --short
git log -1 --format="%h %s"
```

Compare with the handover:
- Branch matches the handover branch → good.
- Branch differs → warn: `⚠️ Current branch ({current}) differs from handover branch ({handover-branch})`.
- If the handover listed uncommitted files → confirm they still appear in `git status`.

---

## Step 3: Load Referenced Context

Read every file listed in the handover's **References** and **Context Needed** sections — these are the files the previous agent flagged as required to continue.

If the project keeps a cross-session memory file at `.claude/context/project-context.md`, read it and note anything added recently.

### Context Loading Strategy

| When | What to load |
|------|--------------|
| Always | `CURRENT.md`, `project-context.md` (if present) |
| If a task/story file is referenced | That file |
| If "Context Needed" lists files | Each file named there |
| On user request only | Large planning docs, full architecture, specs |

Load eagerly — better to have too much context than too little at session start.

---

## Step 3.5: Validate Continuity

Cross-check before displaying the brief. Surface only failures, not confirmations:

| Check | Action if failed |
|-------|-----------------|
| Files listed in References exist on disk | Warn which paths are missing |
| Branch in handover matches current branch | Warn of the mismatch — do not assume either is correct |
| Uncommitted files in handover still appear in `git status` | Note if they were committed or disappeared |

---

## Step 4: Display Resume Brief

### Resume mode (handover found):

```
📋 Session resumed — {handover datetime} ({X min/hours ago})
   Written by: {agent from handover header}

┌─────────────────────────────────────────────────┐
│  Focus:    {task/story + short title}           │
│  Branch:   {branch-name}                        │
│  State:    {mid-task | task complete | blocked} │
└─────────────────────────────────────────────────┘

Resume Point:
{resume point from CURRENT.md, verbatim}

Uncommitted files from last session:
{list, or "None — working tree was clean"}

What happened last session:
{bullet list from CURRENT.md}

Decisions to carry forward:
{decisions from CURRENT.md}

Context loaded:
  ✓ {each file loaded}

⚡ Next Action
{the concrete next step from CURRENT.md}
```

### Fresh orientation mode (no handover, or `fresh` argument):

```
📋 {No previous handover found | Fresh orientation requested}

Git state:
  Branch:  {branch}
  Status:  {clean | N uncommitted files}
  Last:    {last commit}

⚡ Suggested next step:
  {infer from recent commits / open files, or ask the user what to work on}
```

---

## Notes

- Do not ask clarifying questions — work from what the files contain.
- session-start is orientation only. Do not begin implementation, do not edit files.
- The agent that wrote the handover may differ from the current agent — that is expected.
