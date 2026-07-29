# Step 3 — Verify & Health Report

## Mandatory rules
- Verify every modified/archived file is accessible and intact.
- Confirm no critical information was lost.
- Re-measure, score, and record for next time.

## Sequence

### 1. File integrity
Confirm each modified file exists, is readable, and is valid markdown. Confirm each
archived file exists at its new location and the manifest is accurate.
```
FILE INTEGRITY
  ✓ CLAUDE.md — readable, valid
  ✓ project-context.md — readable, valid
  ✓ CURRENT.md — readable, valid
  ✓ archive manifest — {n} files listed and present
  → PASS
```

### 2. Critical content preserved
Scan modified files for the must-keep items and check them off:
- **CLAUDE.md:** current phase/branch · key commands · tech-stack summary · reference to project-context.md
- **project-context.md:** core patterns · error codes · naming conventions · security rules · anti-patterns
- **CURRENT.md:** current focus · git state · next action

Report anything missing; if a critical section was dropped, restore it.

### 3. Broken references
Scan all context files for links/paths to files that were archived or removed.
List any found and offer to fix (repoint to the archive path, or remove).

### 4. Re-measure
Re-run `wc -l` on every context file. Show before → after → target for each,
plus the new always-loaded subtotal and token estimate.

### 5. Context health score (/100)
- **Target compliance (40):** how close each file is to its target.
- **Archival status (20):** completed work archived · manifest exists · clean active context.
- **Reference integrity (20):** no broken links · valid paths · consistent naming.
- **Content quality (20):** critical info preserved · no redundancy · appropriate detail.

Rating: 90–100 EXCELLENT · 75–89 GOOD · 60–74 FAIR · <60 NEEDS ATTENTION.

### 6. Recommendations
If below 90, list the specific changes that would raise the score. Note when to
run this again (after the next milestone) and which file tends to grow (usually
`CLAUDE.md` during active development).

### 7. Save an optimization record
Write `.claude/archive/optimization-records/{date}.yaml` capturing before/after
line + token totals, actions taken, savings, health score, and the next trigger.

## Final report
```
════════════════════════════════════════════════
CONTEXT OPTIMIZATION COMPLETE — {project} · {date}
  Before → After: {before} → {after} lines (~{pct}% reduction)
  Health score:   {score}/100 ({rating})
  ✓ integrity  ✓ critical content  ✓ references  ✓ archive accessible
  Record saved:   {path}
════════════════════════════════════════════════
```

## Complete
The workflow is done. The user can continue with leaner context and re-run after
the next milestone.
