---
baseline_commit: db3cfb4
---

# Story 13.4d: Impairment stored at the level the filing supports

Status: ready-for-dev

## Story

As Lawrence (investor),
I want any write-down recorded against exactly the level its filing charges it to,
so that a company-level charge is never attributed to a brand the filer never named.

## Scope boundary (read first)

**One outcome: every brand-year has an impairment row whose `level` says what the filing
supports.** Adds a `level` column to 13.4c's `brand_figures`, a formula spec
`brand_impairment_v1.yaml`, and a second write-path stage beside 13.4c's. No mapping-spec version,
no API, no UI. No existing figure changes; 13.4c's carrying-value rows are read, never written.

**Decisions taken before drafting (Lawrence, 2026-10-08, all as recommended):**
- D-e: a CPB brand-year with no filed charge is `insufficient_data` with a reason code
  (`no_impairment_disclosed_for_brand`), never a derived zero — even though CPB's per-brand charges
  sum exactly to its consolidated figure. A derived zero is ThesisTrace originating a number.
- D-f: ZTS's company-wide `ImpairmentOfIntangibleAssetsExcludingGoodwill` is NOT mapped or stored:
  it covers all intangibles, not brands, and mapping it needs a new mapping version (the split
  trigger). ZTS rows carry `level: filer_only` and a reason naming that concept.
- D-g: one impairment row per carrying-value brand-year, plus filed charges that have no
  carrying-value row (CPB Allied Brands FY2025, Late July FY2025).

**Out of scope / deferred:**
- Storing ZTS's company-level figure → its own story, only if 13.7b needs it (needs a mapping bump).
- The 10%-or-less disclosure → 13.4e. Display → 13.7b. Golden entries → 13.6a/b (harness cannot
  express a member). API provenance → 13.7a.
- Any impairment for QSR → none exists in four filings (`story_13_3_brand_member_live_verification`);
  nothing to defer.
- The DoD override names company-facts, which carries no dimensions; verification uses the stored
  Inline-XBRL facts, as in 13.4b/13.4c.

## Acceptance Criteria

1. **Level is stored as data beside the figure.** `brand_figures` gains a nullable `level` column
   (migration revising `f3a8c2d61b47`): `brand` | `filer_only` | `none`. Every impairment row
   carries one; carrying-value rows leave it NULL (13.4c unchanged). Never inferred from which
   table or figure a row sits in.

2. **Levels are declared per filer in the spec and checked against what the pipeline executes.**
   `brand_impairment_v1.yaml` declares each filer's level with a `note` (live evidence) and
   `rationale`. The loader rejects a spec where a filer is `brand` but no dimensioned rule maps
   `brand_intangible_impairment` for it, or where a filer that rule DOES map is not `brand`
   (compared against `DIMENSIONED_RULES`, never against another line of the spec).

3. **The row set.** For each issuer: one `figure: impairment` row for every brand-year that has a
   current carrying-value row (13.4c's `formula_version`, same `mapping_version`), plus one for
   every filed charge whose brand-year has none. A filer with no declared level writes
   `insufficient_data` rows with reason `impairment_level_undeclared`, never a guessed level.

4. **Values only where the filing charges the brand.**
   - `level: brand` and a filed member-level charge → `status: ok`, the filed value, FK to its
     `canonical_member_facts` row (AD-19).
   - `level: brand`, no filed charge for that brand-year → `insufficient_data`,
     reason `no_impairment_disclosed_for_brand` (D-e).
   - `level: filer_only` → `insufficient_data`, reason `impairment_reported_only_at_filer_level`
     naming the concept (D-f).
   - `level: none` → `insufficient_data`, reason `filer_tags_no_impairment`.
   Selection reuses 13.4c's basis/precedence/tie rules; two disagreeing charges for one
   brand-year are `insufficient_data`, never a pick or a sum.

5. **Write path, idempotent, and isolated from carrying value (AD-1).** The stage runs in
   `run_issuer` AFTER 13.4c's stage and before commit, and in `make brands`. Upsert on
   `uq_brand_figures_key`; stale-row deletion scoped to `figure: impairment` and this spec's
   version pair, so it can never delete a carrying-value row (and 13.4c's can never delete
   an impairment row). A second run changes nothing.

6. **Spec conformance.** `inputs: [brand_intangible_impairment]` is the query filter; the
   carrying-value formula version the row set is read from is declared in the spec and read by
   the code; `missing_data_policy: insufficient_data` is the only accepted policy; every reason
   code is declared in the spec and applied by code.

7. **The dev store materializes exactly the expected set** (`concepts_v19`): **88** impairment rows
   — CPB 50 (`brand`), QSR 30 (`none`), ZTS 8 (`filer_only`); **5** `ok` with values equal to
   their source rows (Allied Brands FY2024 53m and FY2025 15m, Pop Secret FY2024 76m, Late July
   FY2025 11m, Snyder's of Hanover FY2025 150m); **83** `insufficient_data`; carrying-value rows
   still 86 and unchanged.

## Tasks / Subtasks

- [ ] **1. Migration + model.** Add nullable `level` (String(16)) to `brand_figures` with a CHECK
      allowing NULL or the three values; mirror both in `BrandFigure`. `make migrate`. (AC 1)
- [ ] **2. Spec.** `brand_impairment_v1.yaml`: `figure: impairment`, `inputs`,
      `missing_data_policy`, `rounding`, `basis` (unqualified only), `row_set_from:
      brand_carrying_value_v1`, `levels` per CIK (CPB `brand`, QSR `none`, ZTS `filer_only`) with
      note/rationale, `reasons` with their codes. Loader checks per AC 2 and AC 6. (AC 2, 6)
- [ ] **3. Materializer.** `materialize_brand_impairments(session, issuer_cik)` in
      `backend/brands/store.py`, reusing 13.4c's identity, `_basis`, `_choose` and upsert/stale
      pattern; returns `{"written", "removed", "unresolved", "insufficient"}`. (AC 3, 4, 5)
- [ ] **4. Wire.** Call after `materialize_brand_carrying_values` in `run_issuer` and in
      `brands/__main__.py`; add to the summary and the `OK` line. (AC 5)
- [ ] **5. Tests** (`tests/test_brand_impairments.py`; seed rows; assert the count first):
  - [ ] each level's outcome and reason code; a filed charge on a brand-year with no carrying row;
        an undeclared filer. (AC 3, 4)
  - [ ] loader rejections: `brand` filer the rule does not map; mapped filer declared otherwise;
        undeclared reason; non-`insufficient_data` policy. (AC 2, 6)
  - [ ] isolation both ways: carrying stage never deletes impairment rows and vice versa; rerun
        idempotent. (AC 5)
  - [ ] wiring: real offline pipeline run writes impairment rows after carrying rows. (AC 5)
  - [ ] migration: Alembic round-trip of the new revision on the guarded test DB; CHECK matches.
- [ ] **6. Mutation audit.** Commit first; extend `scripts/verify_brand_figure_guards.py` with the
      impairment guarantees (level from spec, reason per level, row-set source, stale isolation,
      no derived zero); every mutation fails on an `AssertionError`.
- [ ] **7. Dev-store run.** `make migrate`, `make brands` twice; confirm AC 7's exact counts.
- [ ] **8. Live-data DoD.**
  - [ ] (1) Findings first: `story_13_3_brand_member_live_verification` already live-verified every
        impairment fact (CPB per member, sums = consolidated; ZTS consolidated-only; QSR none).
  - [ ] (2) Coverage against the stored Inline-XBRL facts (AC 7). No new live fetch is needed —
        13.4c's spot-check already confirmed the stored values match the filings, and every value
        here is a stored canonical value. State this in Completion Notes.
  - [ ] (3) Spec notes read before calling any gap a defect (`us-gaap_v18.yaml:719`).
  - [ ] (4) Golden: N/A (→ 13.6a/b). (5) Browser render: N/A — nothing reads `brand_figures` yet.
  - [ ] (6) Record `story_13_4d_impairment_level_materialized` in `engineering-findings.yaml` and
        `CURATED_SECTIONS`. (7) Triage: blocking only if it contradicts an AC.
- [ ] **9. Close.** `make test`, `make lint`; story and sprint status → `review`; commit, push, PR,
      Codex prompt. Do not merge.

## Dev Notes

- **Reuse, don't fork.** 13.4c's `brands/store.py` already has identity resolution, `_basis`,
  `_choose`, the upsert and the scoped stale delete. Factor shared pieces out only as far as both
  stages need; do not change 13.4c's behaviour (its 18-mutation audit must still pass).
- **Stale deletion already filters on `figure`** (13.4c, Codex-verified), which is what makes AC 5's
  isolation hold — keep that filter in the impairment stage too, and test both directions.
- **The live data** (dev store, `concepts_v19`): impairment member rows are CPB only —
  Allied Brands FY2024 53m / FY2025 15m, Pop Secret FY2024 76m, Late July FY2025 11m, Snyder's of
  Hanover FY2025 150m — all unqualified, one per brand-year. Allied FY2025 and Late July FY2025
  have no carrying-value row. CPB FY2022/FY2023 carry no impairment concept at all.
- **AD-16 and the Cameco rule:** a charge not filed for a brand is an explained absence, never 0.
- **Previous-story lessons:** assert counts before contents; commit before mutating; compare every
  validator against something executed; Codex finds real issues — re-check status fields after it.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### Change Log

### File List
