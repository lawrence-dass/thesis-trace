---
baseline_commit: 742b769
---

# Story 13.5b: Segment figures materialized into their own store

Status: review

## Story

As Lawrence (developer),
I want segment payloads computed and stored with their own key,
so that per-segment figures cannot collide in a table whose key carries no segment.

## Scope boundary (read first)

**One outcome: a `segment_payloads` table, derived on the write path from the segment rows 13.5a
lands in `canonical_member_facts`, with its own key and member-level provenance, idempotent under
the daily cron.** One migration, one materializer stage wired into the pipeline after the brand
stages, one CLI. No mapping or formula spec change, no API or UI.

**Decisions (Lawrence, 2026-10-10, all as recommended):**
- D-k: **no formula spec** — a payload is a filed value carried through, nothing is computed, so the
  key is exactly the AC's: issuer, axis, member, canonical concept, fiscal year, mapping version.
  The inputs are derived from what the pipeline executes (every concept a segment rule produces,
  every member in `SEGMENT_MEMBERS`), never declared a second time.
- D-l: **a qualified row vetoes its segment-year** — a stored context carrying any axis besides the
  segment axis (e.g. a geography breakdown within a segment) is a different measurement; the
  segment-year is stored `insufficient_data` with the qualifier named, never a pick. Same rule as
  13.4c's F1 (an unknown qualifier vetoes the whole brand-year).
- D-m: **a year nobody filed writes no row** — absence is not defaulted (AD-16); a filer-level
  `insufficient_data` (no segment axis, one generic member) is 13.5c's AC, not this one.

**Evidence already gathered (dev store, 2026-10-10 — no fetch):** under `concepts_v20` CPB has 48
non-superseded segment rows — 3 concepts × 2 segments × FY2018-2025, 48 distinct
(concept, member, year), every context single-axis, every unit USD. Expected materialization: 48
`ok` rows, 0 insufficient.

**Out of scope / deferred:** segment-kind as data, and filer-level insufficiency → 13.5c; QSR's
segment-axis members are BRANDS (`segment_brand_members`), never segment payloads; golden entries →
13.6a/b; display → 13.7b.

## Acceptance Criteria

1. **Own table, own key.** `segment_payloads` has a unique key on (issuer_cik, axis, member_key,
   canonical_concept, fiscal_year, mapping_version), a status CHECK (ok ⇒ value; insufficient_data
   ⇒ no value and a reason), and member-level provenance: `source_member_fact_id` (FK to
   `canonical_member_facts`), `member_as_filed`, accession, period end, unit.
2. **Derived from executed declarations only.** The materializer reads non-superseded rows of the
   running `MAPPING_VERSION`, for concepts produced by a segment rule and members in
   `SEGMENT_MEMBERS`, on that filer's segment axis. Brand rows (including QSR's segment-axis brands)
   never become payloads.
3. **One value per segment-year, never a pick.** A segment-year with one unqualified row stores it
   `ok`, value carried exactly; any qualified row vetoes the segment-year (D-l).
4. **Idempotent.** A second run writes the same rows and changes nothing; a segment-year that stops
   resolving under the same mapping version is removed; rows under another mapping version are never
   touched.
5. **Wired.** The pipeline runs the stage per issuer before commit (summary key `segments`); a CLI
   (`make segments`) materializes every issuer.
6. **Dev store.** `make migrate` then `make segments` writes exactly 48 `ok` rows for CPB matching
   their source rows value-for-value; a second run reports 0 removed and identical rows.

## Tasks / Subtasks

- [x] **1. Migration + model.** `segment_payloads` per AC 1; migration test replays the chain and
      compares constraints to the model.
- [x] **2. Materializer** `backend/segments/store.py` (`materialize_segment_payloads`) per AC 2-4:
      upsert on the key refreshing every non-key column and `computed_at`; stale delete scoped to
      issuer + mapping version.
- [x] **3. Wiring.** `pipeline/run.py` stage; `backend/segments/__main__.py`; `make segments`.
- [x] **4. Tests** (counts first): AC 1-5, incl. a QSR segment-axis brand row ignored, a qualified
      row vetoing, other-version rows untouched, a second pass unchanged, the pipeline test.
- [x] **5. Mutation audit** `scripts/verify_segment_payload_guards.py` (commit tests first).
- [x] **6. Dev store + DoD.** AC 6 exact, by a query comparing payloads to source rows. Findings
      checked first; live fetch N/A (13.5a spot-checked these exact rows, values carried unchanged);
      golden N/A (→ 13.6a/b); browser N/A (nothing renders); record
      `story_13_5b_segment_payloads_materialized` (+ `CURATED_SECTIONS`).
- [x] **7. Close.** `make test`, `make lint`, all audits; status `review`; commit, push, PR, Codex
      prompt.

## Dev Notes

- Pattern: `brands/store.py` `materialize_brand_carrying_values` — upsert on a named constraint,
  `computed_at=func.now()`, stale delete scoped to the version pair; `brands/__main__.py` for the
  CLI (tests monkeypatch `get_sessionmaker`).
- Segment axis per filer: `SEGMENT_AXES` / `SEGMENT_MEMBERS` (13.5a review F1). A row is a segment
  row iff `(issuer, axis_as_filed) in SEGMENT_AXES` and its `member_key` is a declared segment.
- Migration head: `a9d3e7f25c18` (brand_figures level).
- Lessons: assert counts first; commit tests before mutating; the harness must rebind names that
  `pipeline/run.py` imports by name; a test whose seeded rows sit on the key the run writes passes
  for the wrong reason (13.4c).

## Dev Agent Record

### Agent Model Used

claude-opus-5-5

### Completion Notes List

- AC 1-5: `segment_payloads` (migration `c4e8b1d93f27`, model `SegmentPayload`);
  `segments/store.py` `materialize_segment_payloads` with inputs from `segment_inputs()`
  (SEGMENT_AXES / SEGMENT_MEMBERS / rules on the axis); pipeline stage (summary key `segments`);
  `make segments`. 12 tests (11 payload + 1 migration round-trip), counts asserted first.
- The pipeline test runs the real CPB FY2025 instance fixture: 18 payloads (3 concepts × 2
  segments × FY2023-25), each matched to a fact in the instance, independent of canonicalization.
- Mutation audit `scripts/verify_segment_payload_guards.py`: 11/11 killed (installs the mutant
  in sys.modules so `pipeline/run.py`'s by-name import binds it).
- AC 6 (dev store): 48 `ok` payloads, 48/48 match their source rows on every provenance field,
  0 source rows unmaterialized; second run wrote 48, removed 0.
- DoD: findings checked (13.5a's entry); live fetch N/A (values carried unchanged from rows 13.5a
  spot-checked live); golden N/A (→ 13.6a/b); browser N/A (nothing renders); recorded
  `story_13_5b_segment_payloads_materialized`. Also recorded 13.5a's Codex-round learning
  (`a_rule_axis_is_not_an_identity_axis`). Triage: nothing blocking, nothing deferred.

### Change Log

- 2026-10-10 — Story file created; D-k..D-m decided as recommended; implemented, verified on the
  dev store, status → review.

### File List

- `db/migrations/versions/c4e8b1d93f27_add_segment_payloads.py` (new)
- `backend/app/models.py`
- `backend/segments/__init__.py`, `store.py`, `__main__.py` (new)
- `backend/pipeline/run.py`
- `Makefile`
- `backend/tests/test_segment_payloads.py`, `test_segment_payload_migration.py` (new)
- `backend/tests/test_sprint_status.py`
- `scripts/verify_segment_payload_guards.py` (new)
- `_bmad-output/implementation-artifacts/engineering-findings.yaml`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/13-5a-cpb-s-segment-concepts-mapped.md` (status → done)
- `_bmad-output/implementation-artifacts/13-5b-segment-figures-materialized-into-their-own-store.md`
