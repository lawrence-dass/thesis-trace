---
description: 'Archive the current handover and start a clean one. Use between epics/phases.'
---

# Session Archive — Reset Handover

A lightweight companion to `/session-end`. Use it when you want to close out a
chapter of work (an epic, a milestone, a phase) and start the next one with a
clean, minimal handover instead of a long running one.

---

## Steps

1. Read `.claude/handoff/CURRENT.md`.
   - If it does not exist, output "Nothing to archive." and stop.

2. Copy it verbatim to `.claude/handoff/archive/{YYYY-MM-DD}.md`.
   - Create the `archive/` directory if needed.
   - If a file for today already exists, append `-2`, `-3`, … to avoid overwriting.

3. Write a fresh, minimal `.claude/handoff/CURRENT.md` containing only:

```markdown
# Handover — {YYYY-MM-DD HH:MM} | {agent name + model}

## Mode
General handover (fresh start)

## Focus
- **Phase**: {current phase / milestone}
- **Branch**: {branch-name}

## Next Action
{The single immediate next step, carried over from the archived file.}

## References
- Previous handover: `.claude/handoff/archive/{YYYY-MM-DD}.md`

---
*Reset by /session-archive — {YYYY-MM-DD HH:MM}*
```

4. Confirm:

```
✅ Archived → .claude/handoff/archive/{date}.md
✅ Fresh CURRENT.md created

Carried forward: {one-line next action}
```

---

## Notes

- This is a deliberate reset, not a normal handoff. For everyday end-of-session
  saves, use `/session-end` (which already keeps timestamped copies).
- Everything from the old handover stays retrievable in `archive/`.
