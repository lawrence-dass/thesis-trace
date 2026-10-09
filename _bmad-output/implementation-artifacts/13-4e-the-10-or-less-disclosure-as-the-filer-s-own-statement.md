---
baseline_commit: c9c897a
---

# Story 13.4e: The 10%-or-less disclosure, as the filer's own statement

Status: done

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

- [x] **1. Spec + loader guard.** `brand_ten_percent_disclosure_v1.yaml` (inputs
      `[trade_names_within_ten_percent_of_impairment]`, `allowed_kinds: [disclosure]`, caveat
      `filer_defined_threshold`). In `brands/store.py`: `parse_spec` reads optional `allowed_kinds`
      (each must be a kind the mapping spec declares) and the new caveat; the stage writes
      `insufficient_data` for a disallowed kind and applies `filer_defined_threshold` to every `ok`
      row when declared. Carrying-value behaviour unchanged. (AC 1, 2)
- [x] **2. Wire.** Call the stage with the disclosure formula version in `run_issuer` (summary key
      `brand_disclosures`) and `make brands`. (AC 4)
- [x] **3. Tests** (`tests/test_brand_disclosures.py`, counts first): both spellings → one key, 4
      rows; a disallowed kind → insufficient; caveat on every ok row; isolation from carrying and
      impairment rows; idempotent; loader rejects an undeclared kind; pipeline wiring. (AC 1-4)
- [x] **4. Mutation audit.** Commit first; extend an audit with: kind guard off, caveat dropped,
      stage not wired. 13.4c and 13.4d audits must still pass.
- [x] **5. Dev-store run + DoD.** `make brands` twice; AC 5 exact. Findings first
      (`story_13_3_brand_member_live_verification` live-verified both spellings); no new fetch
      (values are stored facts already verified); golden N/A; browser N/A; record
      `story_13_4e_ten_percent_disclosure_materialized` (+ `CURATED_SECTIONS`).
- [x] **6. Close.** `make test`, `make lint`; status `review`; commit, push, PR, Codex prompt.

## Dev Notes

- 13.4c's stage: `materialize_brand_carrying_values(session, cik, formula_version=...)` reads the
  spec's `inputs`, `figure`, `basis`, `caveats`. 13.4c and 13.4d audits anchor on its source — keep
  their anchor lines byte-identical (`scripts/verify_brand_figure_guards.py`).
- Kinds declared in the mapping spec: `MEMBER_KINDS` (`canonicalization/mappings/engine.py`).
- Lessons: assert counts first; commit before mutating; rebind `from x import f` names in a
  mutation harness; a validator must compare against something executed.

## Dev Agent Record

### Agent Model Used

Claude Opus 5.5 (`claude-opus-5-5`), via the dev-story workflow.

### Completion Notes List

- **AC 1.** No threshold of ours: nothing in `backend/brands/` encodes 10% (asserted by
  `test_no_ten_percent_threshold_is_encoded_anywhere`); every stored row carries
  `filer_defined_threshold`, and the spec's `rationale` says the band is Campbell's.
- **AC 2.** New spec field `allowed_kinds` in 13.4c's `parse_spec`, checked against the mapping
  spec's `MEMBER_KINDS`; a row resolving to another kind is `insufficient_data` naming it. The
  carrying-value spec declares no `allowed_kinds` and never reads this concept (unchanged).
- **AC 3.** Both spellings land under `within_ten_percent_coverage`, each FK'd to its member as filed.
- **AC 4.** Same stage, own formula version and figure; wired after impairment in `run_issuer`
  (`brand_disclosures` summary key) and `make brands`. Second run: 0 removed at every stage.
- **AC 5.** Exact: 4 rows (434m, 434m, 1,293m, 2,587m), all ok, all equal to source; carrying 86
  and impairment 88 unchanged.
- **Audits.** New `scripts/verify_brand_disclosure_guards.py` 4/4 killed; 13.4c 18/18 and 13.4d
  12/12 still killed (no anchor line in `store.py` moved).
- **DoD.** Findings first (13.3 live-verified both spellings); no new fetch; golden N/A
  (→ 13.6a/b); browser N/A (nothing reads `brand_figures` yet); recorded
  `story_13_4e_ten_percent_disclosure_materialized`. Deferred, recorded there: the impairment
  loader accepts caveats its stage never applies (none shipped) — a one-line follow-up.
- `make test`: 650 passed. `make lint`: clean.

#### Codex review round (2026-10-09; tests `1c46a31` red, fix `b02ae4f`)

5 regression cases committed first and seen red, then fixed.
- **F1 (BLOCKING, AC 1).** `filer_defined_threshold` was applied only to `ok` rows; an
  insufficient disclosure row (unknown qualifier, or a disallowed kind) carried `caveats=[]`. Now
  on every row of the figure.
- **F2 (deferrable, fixed).** The impairment loader accepted this story's `allowed_kinds` and never
  enforced it — the same shape as the caveat finding this story had deferred. One guard closes
  both: `parse_impairment_spec` rejects any caveat or `allowed_kinds`. No figure changed.
- **F3 (deferrable, fixed).** `make brands`' disclosure call had no test; one now drives
  `brands.__main__.main` against the guarded test DB.
- Audits: disclosure 7/7 (3 new cases), impairment 12/12, carrying value 18/18. `make test` 656
  passed, lint clean. Dev store unchanged (86 / 88 / 4; only disclosure rows carry the caveat).

### Change Log

- 2026-10-08 — Story file and implementation: disclosure spec, `allowed_kinds` guard, filer-threshold
  caveat, wiring, 8 tests, 4-case audit; dev store verified. No existing figure changed.
- 2026-10-09 — Codex round: caveat on every disclosure row; impairment loader rejects unapplied
  caveats/allowed_kinds (closing the deferred finding); CLI wiring test; 3 audit cases.

### File List

- `backend/formulas/specs/brand_ten_percent_disclosure_v1.yaml` (new)
- `backend/brands/store.py`
- `backend/brands/__main__.py`
- `backend/pipeline/run.py`
- `backend/tests/test_brand_disclosures.py` (new)
- `backend/tests/test_sprint_status.py`
- `scripts/verify_brand_disclosure_guards.py` (new)
- `_bmad-output/implementation-artifacts/engineering-findings.yaml`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/13-4d-impairment-stored-at-the-level-the-filing-supports.md` (status → done)
- `_bmad-output/implementation-artifacts/13-4e-the-10-or-less-disclosure-as-the-filer-s-own-statement.md`
