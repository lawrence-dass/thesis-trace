---
baseline_commit: c9c897a
---

# Story 13.4e: The 10%-or-less disclosure, as the filer's own statement

Status: in-progress

## Story

As Lawrence (investor),
I want CPB's filed early-warning disclosure stored and labelled as CPB's,
so that a brand approaching a write-down is visible before one lands, with no threshold invented by
ThesisTrace.

## Scope boundary (read first)

**One outcome: CPB's "trade names within 10% of impairment" aggregate, materialized per year as the
filer's own statement.** A second spec, `brand_ten_percent_disclosure_v1.yaml`, run through 13.4c's
existing stage (`materialize_brand_carrying_values` is already parametrized by `formula_version`),
plus a guard that rows under it can only be the spec's `disclosure` kind. No migration, no mapping
version, no API or UI. No existing figure changes.

**No decision needed from Lawrence.** Nothing is ambiguous: four filed values, one stable member key
across both spellings, no qualifiers, and no threshold of ThesisTrace's anywhere.

**Out of scope / deferred:** display and its "filer's own statement" wording → 13.7b; golden entries
→ 13.6a/b; API provenance → 13.7a. Whether the disclosure can be broken down by brand → it cannot:
the filing never says which trade names qualify (that is why it is an aggregate).

## Acceptance Criteria

1. **No ThesisTrace threshold.** The 10% band is CPB's filed number; nothing in the code or spec
   computes, compares against or encodes "10%". Every stored row carries caveat
   `filer_defined_threshold`, and the spec's `rationale` says the threshold is the filer's.
2. **Stored as the aggregate it is.** Rows land in `brand_figures` with `figure:
   ten_percent_or_less_disclosure`, `brand_key: within_ten_percent_coverage`, `kind: disclosure`.
   The spec declares the only kinds it may store (`disclosure`); a row that resolves to any other
   kind is `insufficient_data` naming the kind, never stored as a brand. The carrying-value spec
   never reads this concept (13.4c, unchanged).
3. **The rename is invisible.** FY2022-23 (`...With10OrLess...`) and FY2024-25
   (`...WithTenPercentOrLess...`) land under one `brand_key`, each row FK'd to the member fact as
   filed (AD-19).
4. **Write path, same key, idempotent (AD-1, NFR-8).** Runs in `run_issuer` and `make brands` after
   carrying value, under 13.4c's upsert key and figure-scoped stale delete. A second run changes
   nothing; neither the carrying-value nor the impairment rows are touched.
5. **Dev store** (`concepts_v19`): exactly **4** rows, CPB FY2022 434m, FY2023 434m, FY2024 1,293m,
   FY2025 2,587m, each `ok`, each equal to its source; carrying value (86) and impairment (88)
   unchanged.

## Tasks / Subtasks

- [ ] **1. Spec + loader guard.** `brand_ten_percent_disclosure_v1.yaml` (inputs
      `[trade_names_within_ten_percent_of_impairment]`, `allowed_kinds: [disclosure]`, caveat
      `filer_defined_threshold`). In `brands/store.py`: `parse_spec` reads optional `allowed_kinds`
      (each must be a kind the mapping spec declares) and the new caveat; the stage writes
      `insufficient_data` for a disallowed kind and applies `filer_defined_threshold` to every `ok`
      row when declared. Carrying-value behaviour unchanged. (AC 1, 2)
- [ ] **2. Wire.** Call the stage with the disclosure formula version in `run_issuer` (summary key
      `brand_disclosures`) and `make brands`. (AC 4)
- [ ] **3. Tests** (`tests/test_brand_disclosures.py`, counts first): both spellings → one key, 4
      rows; a disallowed kind → insufficient; caveat on every ok row; isolation from carrying and
      impairment rows; idempotent; loader rejects an undeclared kind; pipeline wiring. (AC 1-4)
- [ ] **4. Mutation audit.** Commit first; extend an audit with: kind guard off, caveat dropped,
      stage not wired. 13.4c and 13.4d audits must still pass.
- [ ] **5. Dev-store run + DoD.** `make brands` twice; AC 5 exact. Findings first
      (`story_13_3_brand_member_live_verification` live-verified both spellings); no new fetch
      (values are stored facts already verified); golden N/A; browser N/A; record
      `story_13_4e_ten_percent_disclosure_materialized` (+ `CURATED_SECTIONS`).
- [ ] **6. Close.** `make test`, `make lint`; status `review`; commit, push, PR, Codex prompt.

## Dev Notes

- 13.4c's stage: `materialize_brand_carrying_values(session, cik, formula_version=...)` reads the
  spec's `inputs`, `figure`, `basis`, `caveats`. 13.4c and 13.4d audits anchor on its source — keep
  their anchor lines byte-identical (`scripts/verify_brand_figure_guards.py`).
- Kinds declared in the mapping spec: `MEMBER_KINDS` (`canonicalization/mappings/engine.py`).
- Lessons: assert counts first; commit before mutating; rebind `from x import f` names in a
  mutation harness; a validator must compare against something executed.

## Dev Agent Record

### Agent Model Used

### Completion Notes List

### Change Log

### File List
