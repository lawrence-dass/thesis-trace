---
title: 'Story 13.4b exclusion review fixes'
type: 'bugfix'
created: '2026-10-08'
status: 'in-review'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

Fix all findings from PR #151's review: prevent exclusions with one issuer/axis/alias
identity from silently overwriting each other, and protect canonicalizer and loader wiring
with regression tests. Record behavioral red/green evidence for AC6. Keep Story 13.4b
and its sprint entry at `review`; preserve frozen mapping specs and unrelated user changes.

</frozen-after-approval>

## Implementation Notes

- Reject colliding exclusion identities, naming both decisions, rather than combining
  independently declared scopes. Reuse that guard during full spec validation.
- Exercise `canonicalize_issuer` with real seeded facts and additional applicable rules;
  exercise `load_mapping_spec` with copied temporary specs and isolated cache state.
- Run mutations in isolated processes without rewriting tracked files. Compare the
  stored v18/v19 rows read-only and run the complete backend suite and lint.
- Implemented the duplicate-identity guard in `mappings/engine.py`, 12 new unit/loader
  cases and two seeded pipeline cases. Six collision cases failed before the guard.
- Added `scripts/verify_exclusion_guards.py`: all six isolated mutations produce the
  expected 17 behavioral failures; collection/setup errors and skips reject the audit.
- Verification: 586 backend tests pass; backend and audit-script lint pass. Dev-store
  v18/v19 values and provenance are identical for 96 rows, with 0 unmapped-member issues.
- Independent production/test and audit-script reviews found no remaining issues.
  Recorded full evidence in the existing story. Its status and sprint entry remain
  `review`; this implementation record remains `in-review` until merge.
