---
baseline_commit: b47bd18
---

# Story 13.5a: CPB's segment concepts, mapped

Status: in-progress

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

- [ ] **1. Epic AC corrections** (overtaken by events; headings untouched): 13.5a AC 2 →
      stored Inline XBRL + live instance spot-check; 13.5b's `segment_payloads` → a derived store
      over `canonical_member_facts` (D-h).
- [ ] **2. Engine.** Load `segment_members` (reuse `BrandMember` with kind `segment`; add `segment`
      to `MEMBER_KINDS`); pass to `_resolve_members` with brand members; keep them out of
      `BRAND_MEMBERS`; loader checks per AC 2. Segment members resolve only rules on their own axis.
- [ ] **3. Spec.** Copy `us-gaap_v18.yaml` → `us-gaap_v19.yaml`; add the three dimensioned concepts
      (CPB-scoped), the two segment members, the two Corporate exclusions, notes per AC 1/6;
      registry → `concepts_v20` with a HISTORY entry. Never edit v18.
- [ ] **4. Tests** (counts first): both eras resolve to one concept per segment-year; overlap year
      yields one row, no ambiguity issue; Corporate excluded silently; segment member invisible to
      `resolve_brand_identity`; loader rejections; QSR's segment-axis brand identity unaffected.
- [ ] **5. Mutation audit** (commit first): segment members leaking into BRAND_MEMBERS; era source
      dropped; Corporate exclusion removed; axis restriction removed.
- [ ] **6. Dev store.** `make migrate` (none expected), `make py F=scripts/recanonicalize.py`,
      `make brands`; AC 4 and AC 5 exact, from `scripts/segment_axis_coverage.py` and a query.
- [ ] **7. Live-data DoD.** Findings first (`cpb_segment_members_stable_but_tags_switch`); live
      spot-check, named before fetching: CPB `0000016732-25-000112` (FY2025: SegmentOperatingEarnings
      + SegmentExpenditureAdditionToPPE) and `0000016732-23-000109` (FY2023: OperatingIncomeLoss +
      PaymentsToAcquirePPE) — one segment each; golden N/A (→ 13.6a/b); browser N/A (nothing renders);
      record `story_13_5a_cpb_segment_concepts_mapped` (+ `CURATED_SECTIONS`), and correct
      `cpb_segment_members_stable_but_tags_switch` (per-filing vs per-period boundaries).
- [ ] **8. Close.** `make test`, `make lint`, all three brand audits still pass; status `review`;
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

### Completion Notes List

### Change Log

### File List
