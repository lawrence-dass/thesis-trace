---
name: optimize-context
description: Audit and optimize a project's context files for efficient token usage. Run after a milestone/phase to keep always-loaded context lean without losing critical information.
---

# Optimize Context

**Goal:** Analyze, trim, and verify the files that get loaded into the model's
context so token usage stays lean while output quality is preserved. Run this
after a milestone, epic, or phase completes.

**Your role:** a context-optimization specialist. Audit the context files,
identify savings, and execute them with the user's approval — never lose
critical information to save tokens.

---

## Architecture

Micro-file workflow. Each step is a self-contained file with embedded rules.
Progress sequentially and **never advance past a step until the user approves it.**

---

## Context File Targets

Adapt these to your project. The defaults assume the conventions this kit uses:

| File | Purpose | Target |
|------|---------|--------|
| `CLAUDE.md` | Entry point, current status, rules index | < 60 lines |
| `.claude/context/project-context.md` | Durable implementation rules / patterns | < 200 lines |
| `.claude/handoff/CURRENT.md` | Session handoff | < 50 lines |
| Active task/story files | Per-task working context | < 400 lines each |
| Large planning / architecture docs | Reference material | Load on demand only |

**Token estimation** (rough, varies with density): dense code/config ≈ 15–20
tokens/line · prose ≈ 20–25 · mixed ≈ ~20. Always **measure** lines with `wc -l`;
never estimate file size.

---

## Categories

- **A — Always-loaded** (`CLAUDE.md`, `project-context.md`, `CURRENT.md`): minimize aggressively; every token counts every session.
- **B — On-demand** (active task files, architecture index/shards): keep lean, don't over-compress.
- **C — Reference-only** (completed task files, full plans, validation reports): archive; never load routinely.

---

## Execution

Load and run `steps/step-01-audit.md` to begin. Discovery and measurement happen there.
