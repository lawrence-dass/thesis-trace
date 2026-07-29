# Step 1 — Context Audit & Analysis

## Mandatory rules
- ALWAYS measure file sizes with `wc -l`; never estimate.
- Calculate token impact (lines × ~20 tokens/line).
- PRESENT findings before recommending actions.
- Identify what can be archived vs. what must stay active.
- No time estimates — focus on token savings.

## Task
Audit every context file and produce an optimization report.

### 1. Discover the context files
Locate the Category A/B/C files (see SKILL.md). Confirm which exist:
```bash
for f in CLAUDE.md .claude/context/project-context.md .claude/handoff/CURRENT.md; do
  test -f "$f" && printf "%-45s %s lines\n" "$f" "$(wc -l < "$f")" || echo "$f  MISSING"
done
```
Also list active task files and any large planning/architecture docs.

### 2. Measure Category A (always-loaded)
For each file, report:
```
File: {name} | Current: {lines} lines (~{tokens} tok) | Target: {target} | Status: {OVER|AT|UNDER} | Delta: {+/- lines}
```
Give a subtotal: total always-loaded lines and tokens.

### 3. Measure Category B (on-demand, active only)
List active task files with line counts; flag any over target. Measure the
architecture index and shards if present.

### 4. Identify archival candidates (Category C)
List completed-work files that should move to an archive folder, with line counts
and total lines/tokens reclaimable.

### 5. Identify optimization opportunities
Scan for:
- **Duplication** — the same info in multiple files; redundant sections.
- **Bloat** — 2+ examples of the same pattern; verbose explanations; completed TODOs still listed; stale historical notes.
- **Stale content** — references to finished work, outdated status, superseded decisions.

### 6. Present the audit report
```
════════════════════════════════════════════════
CONTEXT AUDIT — {project}  ·  {date}
════════════════════════════════════════════════
ALWAYS-LOADED (Category A)
  File                 Lines  Target  Status  ~Tokens
  CLAUDE.md            {n}    60      {..}    {..}
  project-context.md   {n}    200     {..}    {..}
  CURRENT.md           {n}    50      {..}    {..}
  SUBTOTAL             {n}                    {..}

ON-DEMAND (Category B, active)
  {task files + architecture, with line counts}

ARCHIVAL CANDIDATES (Category C)
  {completed files}  →  TOTAL {n} lines (~{tok} reclaimable)

OPTIMIZATION OPPORTUNITIES
  {specific items with estimated line savings}

POTENTIAL SAVINGS
  From archival:      {lines} (~{tok})
  From optimization:  {lines} (~{tok})
  COMBINED:           {lines} (~{tok})

CONTEXT HEALTH SCORE: {score}/100  — {rationale}
════════════════════════════════════════════════
```

### 7. Present options
```
[A] Archive only        — move completed files to archive (~{tok} saved)
[O] Full optimization   — archive + trim bloated files (~{tok} saved)
[S] Selective           — choose which optimizations to apply
[R] Review details      — show more detail on specific files
[X] Skip                — context is acceptable, no changes
```

## Next step
After the user selects an option, load `step-02-optimize.md`.
**Do NOT proceed until the user explicitly selects an option.**
