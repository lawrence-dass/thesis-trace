# Step 2 — Execute Optimizations

## Mandatory rules
- NEVER delete without explicit confirmation. Archive = **move**, not delete.
- ALWAYS show a diff preview before applying any file change.
- PRESERVE critical information — trim bloat, not substance.
- Confirm each category of change before executing.

## Handle the user's Step-1 selection
- **[A] Archive only** → run the archival procedure, skip trimming.
- **[O] Full optimization** → archival + all trimming below.
- **[S] Selective** → present each category for individual Y/N approval.
- **[R] Review details** → show file contents, then re-present the options.

---

## Archival procedure
1. Ensure an archive folder exists, e.g. `.claude/archive/{milestone}/`.
2. Write an `archive-manifest.md` recording each moved file (original path →
   archive path → line count) and the reason/date.
3. For each completed file: move it, log it, verify it exists at the destination,
   and only then remove the original.
4. Report:
   ```
   Archiving {milestone}…
     ✓ Moved: {file}
     ✓ Created: archive-manifest.md
   Archived {n} files ({lines} lines, ~{tok} tokens)
   ```

---

## Trimming procedures
For each file, show a diff preview (current lines → new lines → savings) and ask
**Apply? [Y/N]** before writing.

**CLAUDE.md** (target < 60): remove completed status history (keep current only),
consolidate repeats, replace inline content with terse reference links.
*Preserve:* current phase/branch status, key commands, rule references, tech-stack summary.

**project-context.md** (target < 200): keep max one example per rule, consolidate
overlapping rules, drop rules already living in architecture/reference docs.
*Preserve:* core patterns, error codes, naming conventions, security rules, anti-patterns.

**CURRENT.md** (target < 50): keep only current session state; drop historical
decisions unless actively relevant; collapse git state into one block.
*Preserve:* current focus, active blockers, git branch/commit, immediate next action.

**Active task files** (target < 400 each): move completed-task detail to a dev-notes
archive; condense verbose acceptance criteria; drop detail already in code comments.
*Preserve:* acceptance criteria, current task status, blockers, dependencies.

---

## Selective mode
If the user chose **[S]**, present each category as its own gate:
```
Category {n}: {name}
  Savings: {lines} (~{tok})
  Apply? [Y / N / D for details]
```

---

## Track every change
Keep a running log for the verification step:
```yaml
optimization_log:
  date: {date}
  mode: {archive_only | full | selective}
  archived: [{file, from, to, lines}]
  modified: [{file, before_lines, after_lines, changes}]
  skipped:  [{file, reason}]
  totals: {files_archived, files_modified, lines_saved, tokens_saved}
```

## Completion summary
```
OPTIMIZATION COMPLETE
  Archived:  {n} files, {lines} lines removed from active context
  Trimmed:   {n} files, {lines} lines reduced
  Before → After: {before} → {after} lines (~{pct}% reduction)

[V] Verify   [U] Undo all   [R] Review changes
```

## Next step
After the user selects **[V]**, load `step-03-verify.md`.
**Do NOT proceed until the user selects [V].**
