---
baseline_commit: b47bd18
---

# Story 13.5a: CPB's segment concepts, mapped

Status: review

## Story

As Lawrence (developer),
I want CPB's segment figures mapped, including both verified tag switches,
so that segment payload computation has mappings to consume rather than assuming them.

## Scope boundary (read first)

**One outcome: CPB's segment revenue, operating earnings and capex land in
`canonical_member_facts`, per segment, across both tag switches.** One mapping version
(`us-gaap_v19`, `concepts_v20`), one new spec mechanism (`segment_members`), no new table, no API
or UI, no derived figure. Every existing canonical row is reproduced identically under the new
version.

**Decisions (Lawrence, 2026-10-09, all as recommended):**
- D-h: filed segment facts land in `canonical_member_facts` through canonicalization, via a new
  `segment_members` declaration kept SEPARATE from `brand_members`, so 13.4a's brand resolver
  never sees a segment. 13.5b becomes a DERIVED store (the `brand_figures` pattern); its epic AC
  is corrected in this change (Task 1).
- D-i: three concepts — Revenues, segment operating earnings, segment capex.
- D-j: Corporate members on the segment axis are `excluded_members` (13.4b's axis-scoped kind),
  never segments.

**Evidence already gathered (dev store, stored Inline XBRL, 2026-10-09 — no fetch):**
- Both switches are RELABELS: in every overlap year the old and new tag carry identical values per
  segment — operating earnings 4/4 (FY2023-24), capex 6/6 (FY2022-23). Bucketed on period end.
- The recorded "exact boundaries" were per FILING; per PERIOD the tags overlap: operating earnings
  `us-gaap:OperatingIncomeLoss` 2018-2024 / `cpb:SegmentOperatingEarnings` 2023-2025 (first filed
  FY2025); capex `us-gaap:PaymentsToAcquirePropertyPlantAndEquipment` 2018-2023 /
  `cpb:SegmentExpenditureAdditionToPPE` 2022-2025 (first filed FY2024).
- Members: `cpb:MealsBeveragesMember` and `cpb:SnacksMember` on every year FY2018-25.
  `us-gaap:CorporateAndOtherMember` (2019-21) and `us-gaap:CorporateNonSegmentMember` (2018-20) vary.
- The ASU 2023-07 hypothesis, tested against QSR (AC 3): CONFIRMED for the significant-expense
  additions — QSR (calendar) first tags segment COGS and
  `SegmentExpenditureAdditionToLongLivedAssets` in its FY2024 10-K and CPB (Aug FYE) its segment
  COGS / `SegmentOperatingEarnings` / `SegmentReportingOtherItemAmount` in FY2025: each the first
  fiscal year beginning after 2023-12-15, each with restated comparatives. REFUTED for CPB's capex
  switch, first filed FY2024 — a year before CPB's adoption. ZTS tagged segment COGS from FY2019 (no
  switch).

**Out of scope / deferred:** derived segment payloads → 13.5b; segment-kind as data → 13.5c; other
segment-axis concepts (D&A, goodwill, segment COGS) → a later story if 13.7b needs them; QSR/ZTS
segment mapping → not in this story's title; golden entries → 13.6a/b; display → 13.7b.

## Acceptance Criteria

1. **Both switches carried as per-era sources.** `us-gaap_v19.yaml` maps, for CPB only, on
   `us-gaap:StatementBusinessSegmentsAxis`: `segment_revenue` ← `Revenues`;
   `segment_operating_earnings` ← `OperatingIncomeLoss` and `cpb:SegmentOperatingEarnings`;
   `segment_capex` ← `PaymentsToAcquirePropertyPlantAndEquipment` and
   `cpb:SegmentExpenditureAdditionToPPE`. Each switched pair's `note` carries the overlap-equality
   evidence; in the overlap years canonicalization selects ONE value per (segment, year) by its
   normal AD-3 rules and never flags the equal pair as ambiguous.
2. **Segments are declared as segments.** A new `segment_members` section (CPB: `meals_beverages`,
   `snacks`, each with its alias) resolves only the segment concepts. Segment members never reach
   `BRAND_MEMBERS` or 13.4a's resolver; the loader rejects a segment member that is also a brand
   member, or one whose axis no segment rule reads.
3. **Corporate is known, never a segment.** `us-gaap:CorporateAndOtherMember` and
   `us-gaap:CorporateNonSegmentMember` are CPB `excluded_members` on the segment axis with a reason;
   they write no row and raise no `unmapped_member` issue.
4. **The bump reproduces every existing row.** Re-canonicalizing the dev store under `concepts_v20`
   reproduces all `concepts_v19` member rows identically (same values, same provenance) and adds
   only segment rows; 0 `unmapped_member` issues. `make brands` under `concepts_v20` reproduces 86
   carrying / 88 impairment / 4 disclosure rows with identical values.
5. **Coverage verified per year, on period end.** Stored segment rows cover FY2018-2025 for revenue,
   operating earnings and capex for both segments, checked against the stored Inline-XBRL facts
   (Company Facts carries no dimensions), plus a live spot-check of two instance documents named
   before fetching.
6. **The hypothesis is recorded as tested, not assumed.** The spec `note` states what was confirmed
   (expense additions at the ASU 2023-07 date, two filers) and what was refuted (CPB's capex switch).

## Tasks / Subtasks

- [x] **1. Epic AC corrections** (overtaken by events; headings untouched): 13.5a AC 2 →
      stored Inline XBRL + live instance spot-check; 13.5b's `segment_payloads` → a derived store
      over `canonical_member_facts` (D-h).
- [x] **2. Engine.** Load `segment_members` (reuse `BrandMember` with kind `segment`; add `segment`
      to `MEMBER_KINDS`); pass to `_resolve_members` with brand members; keep them out of
      `BRAND_MEMBERS`; loader checks per AC 2. Segment members resolve only rules on their own axis.
- [x] **3. Spec.** Copy `us-gaap_v18.yaml` → `us-gaap_v19.yaml`; add the three dimensioned concepts
      (CPB-scoped), the two segment members, the two Corporate exclusions, notes per AC 1/6;
      registry → `concepts_v20` with a HISTORY entry. Never edit v18.
- [x] **4. Tests** (counts first): both eras resolve to one concept per segment-year; overlap year
      yields one row, no ambiguity issue; Corporate excluded silently; segment member invisible to
      `resolve_brand_identity`; loader rejections; QSR's segment-axis brand identity unaffected.
- [x] **5. Mutation audit** (commit first): segment members leaking into BRAND_MEMBERS; era source
      dropped; Corporate exclusion removed; axis restriction removed.
- [x] **6. Dev store.** `make migrate` (none expected), `make py F=scripts/recanonicalize.py`,
      `make brands`; AC 4 and AC 5 exact, from `scripts/segment_axis_coverage.py` and a query.
- [x] **7. Live-data DoD.** Findings first (`cpb_segment_members_stable_but_tags_switch`); live
      spot-check, named before fetching: CPB `0000016732-25-000112` (FY2025: SegmentOperatingEarnings
      + SegmentExpenditureAdditionToPPE) and `0000016732-23-000109` (FY2023: OperatingIncomeLoss +
      PaymentsToAcquirePPE) — one segment each; golden N/A (→ 13.6a/b); browser N/A (nothing renders);
      record `story_13_5a_cpb_segment_concepts_mapped` (+ `CURATED_SECTIONS`), and correct
      `cpb_segment_members_stable_but_tags_switch` (per-filing vs per-period boundaries).
- [x] **8. Close.** `make test`, `make lint`, all three brand audits still pass; status `review`;
      commit, push, PR, Codex prompt.

## Dev Notes

- Member binding: `_resolve_members` keys on `(issuer, taxonomy, concept, axis, alias)`
  (`engine.py:747`). A member without `maps_to`/`canonical_concepts` claims every rule on any axis it
  iterates — restrict segment members to rules on their own axis.
- `_identity_axes` (brands/store.py) and `_declared_axes` (brand_identity.py) both union every
  dimensioned rule's axis per filer: CPB gains the segment axis as an identity axis. CPB's brand
  rows carry no segment qualifier today, so no brand figure moves — AC 4 proves it.
- Lessons: spec versions are frozen once stamped — copy, never edit; assert counts first; commit
  before mutating; rebind `from x import f` names in a harness.

## Dev Agent Record

### Agent Model Used

Claude Opus 5.5 (`claude-opus-5-5`), via the dev-story workflow.

### Completion Notes List

- **AC 1.** `us-gaap_v19.yaml`: `segment_revenue`, `segment_operating_earnings`, `segment_capex`,
  CPB-scoped, on the segment axis, both switches as per-era sources. New: a dimensioned source may
  name its `taxonomy` — the cpb: custom tags are stored under taxonomy `cpb`, so a rule taking the
  file's `us-gaap` would never have matched its own facts (found while implementing; not in the
  story text). Overlap years: the originally-filed fact wins; no ambiguity raised (tested).
- **AC 2.** `segment_members` section → `SEGMENT_MEMBERS` (kind `segment`, own axis). Kept out of
  `BRAND_MEMBERS`; resolves only its own axis; brand members never resolve on a filer's segment
  axis. Loader rejects a segment that is also a brand key, one on an axis no rule reads, and an
  alias both segment and excluded.
  **Deviation from Task 2:** `segment` was NOT added to `MEMBER_KINDS` — that set validates BRAND
  kinds and 13.4e's `allowed_kinds`; adding it would let a brand declare itself a segment. A
  separate `SEGMENT_KIND` constant instead.
- **AC 3.** CPB exclusions on the segment axis: `corporate_and_other`, `corporate_non_segment`,
  `restructuring_charges` (the third found by querying which members carry the five source tags).
- **AC 4.** Re-canonicalized under `concepts_v20`: 96 v19 rows IDENTICAL (0 dropped, 0 changed),
  +48 segment rows, 0 new issues, second run adds nothing. `make brands` under v20: 86 / 88 / 4,
  equal to v19 on all 178 pairs.
- **AC 5.** 48 rows = 3 concepts × 2 segments × FY2018-25, no gap (period-end buckets). Live: 5/5
  values match CPB `0000016732-25-000112` and `0000016732-23-000109`.
- **AC 6.** The spec notes record the ASU 2023-07 hypothesis as tested: confirmed for the expense
  additions (CPB, QSR), refuted for CPB's capex switch.
- **Audits.** New `scripts/verify_segment_mapping_guards.py` (mutates engine.py in memory BEFORE
  import, since its guarantees run at import): 6/6 killed. Brand audits unchanged: 18, 12, 7.
  First run: all 6 failed at import (harness defect) and the strict contract refused to count
  them; fixed. One test used `dict[...]` and would crash rather than assert — changed to `.get`.
- **DoD.** Findings first; coverage on stored Inline XBRL + live spot-check; golden N/A
  (→ 13.6a/b); browser N/A (nothing renders); recorded
  `story_13_5a_cpb_segment_concepts_mapped`; corrected `cpb_segment_members_stable_but_tags_switch`
  (per-filing vs per-period boundaries). Triage: nothing blocking, nothing deferred.
- Test pins moved deliberately: mapping version (`test_free_cash_flow_concepts.py`) and the shipped
  exclusion count (`test_brand_member_mapping.py`).
- **Codex review of #158 (2026-10-10)** — 4 blocking, 2 deferrable; all six reproduced, failing
  tests committed first (`15bdf6d`), then fixed:
  - F1: `_identity_axes` (brands/store.py) and `_declared_axes` (brand_identity.py) counted CPB's
    segment axis as BRAND identity, so a segment-qualified brand row stopped blocking. Both now
    skip the new `SEGMENT_AXES`. Dev store: the axis appears on the 48 segment rows only, on no
    brand row — no stored figure changes.
  - F2: a segment axis must be read ONLY by segment rules (scoped to filers that all declare
    segments on it); the old reachability check passed the brand axis.
  - F3: scalar `aliases` rejected (was 23 one-character aliases). F4: unread keys
    (`maps_to`, `canonical_concepts`, `kind`, …) rejected instead of silently dropped.
  - F5/F6: tests pinning original-filed precedence with source priority held equal, and annual
    capex over a quarter. Audit grew 6 → 12 cases (now also mutates `canonicalize.py` and runs
    `test_brand_figures.py`); all killed.
  - Not changed: `_load_brand_members` (13.3) has the same scalar-alias trap; no shipped spec
    triggers it, so it is deferred rather than widened into this story.

### Change Log

- 2026-10-09 — Story file (D-h..D-j); implemented us-gaap_v19 / concepts_v20, `segment_members`,
  per-source taxonomy, Corporate exclusions; 15 tests; 6-case import-time audit; dev store
  re-canonicalized and verified; live spot-check. No existing figure changed.
- 2026-10-10 — Codex review fixes F1–F6; 9 tests added (679 total); audit 12/12.

### File List

- `backend/canonicalization/mappings/engine.py`
- `backend/canonicalization/mappings/__init__.py`
- `backend/canonicalization/mappings/brand_identity.py` (review F1)
- `backend/brands/store.py` (review F1)
- `backend/tests/test_brand_figures.py` (review F1)
- `backend/canonicalization/mappings/specs/us-gaap_v19.yaml` (new)
- `backend/canonicalization/mappings/specs/registry.yaml`
- `backend/tests/test_segment_mapping.py` (new)
- `backend/tests/test_brand_member_mapping.py`
- `backend/tests/test_free_cash_flow_concepts.py`
- `backend/tests/test_sprint_status.py`
- `scripts/segment_axis_coverage.py` (new)
- `scripts/segment_switch_evidence.py` (new)
- `scripts/spot_check_segments.py` (new)
- `scripts/verify_segment_mapping_guards.py` (new)
- `_bmad-output/planning-artifacts/epics.md`
- `_bmad-output/implementation-artifacts/engineering-findings.yaml`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/13-4e-the-10-or-less-disclosure-as-the-filer-s-own-statement.md` (status → done)
- `_bmad-output/implementation-artifacts/13-5a-cpb-s-segment-concepts-mapped.md`
