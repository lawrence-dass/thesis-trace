---
baseline_commit: d4a9021
---

# Story 13.4c: Per-brand carrying value, computed and materialized

Status: review

## Story

As Lawrence (investor),
I want each acquired brand's carrying-value series computed on the write path against a versioned
spec,
so that every figure obeys the deterministic boundary and AD-1's CQRS discipline.

## Scope boundary (read first)

**One outcome: one materialized carrying-value figure per brand per fiscal year.** This story adds
a derived store (`brand_figures`), a formula spec (`brand_carrying_value_v1.yaml`), and one
write-path stage in `pipeline/run.py` that reads `canonical_member_facts`, resolves each row's
identity through 13.4a's `resolve_brand_identity`, and writes the series. It adds **no API, no UI
and no mapping-spec version**. It does not change any existing figure: `canonical_member_facts` is
read-only to this story.

**Why the epic AC changed (decided 2026-10-08, Lawrence).** `epics.md` said this story "WRITES
INTO" the member store. That was written before 2026-09-11, when Story 13.3 took over the store and
canonicalization began writing every FILED per-member value into it itself. What remains for 13.4c
is a DERIVED per-brand series, and it gets its own table: `canonical_member_facts` keeps holding
filed facts only, its key and supersession stay owned by `canonicalize_issuer`, and QSR's rows
(where the brand is a segment, not the member) need a `brand_key` that is not a `member_key`.
Task 1 amends `epics.md` to say so, in the same change.

**Decisions taken before drafting (Lawrence, 2026-10-08, all as recommended):**
- D-a: new `brand_figures` table, reused by 13.4d/13.4e under this story's key.
- D-b: a value filed ONLY as a nonrecurring fair-value measurement (CPB Allied Brands and Pop
  Secret, FY2024) is stored, with its **basis recorded as data** beside the figure.
- D-c: a filed **zero** for a year before the brand was owned (Rao's FY2023, Firehouse Subs FY2020)
  is stored as filed, with a `pre_acquisition_comparative` caveat — annotated, never altered.
- D-d: **level per year only.** No year-over-year deltas in this story.

**Out of scope / deferred** (each has a home):
- Impairment → **13.4d**. The 10%-or-less disclosure (`trade_names_within_ten_percent_of_impairment`)
  → **13.4e**. Both reuse this story's table and key. `brand_intangible_acquired` is not read here.
- Year-over-year or since-acquisition deltas → a later formula version, only if 13.7b needs them.
- Provenance in the API schema → **13.7a**. The section that renders the series → **13.7b**.
- Golden entries → **13.6a/13.6b**. The harness cannot express a dimensioned fact
  (`golden_harness_cannot_reach_dimensioned_member_facts`); this story writes none.
- **The segment-rename exposure** (`deferred_the_segment_rename_exposure`): QSR renaming a segment
  member would give one brand-year two current `canonical_member_facts` rows. It needs a
  `context_key` migration and backfill on the CANONICAL store — a second, figure-moving change, so
  under the split trigger it is **not this story's**. This story's guard (AC 6) turns it into a
  loud `insufficient_data` row rather than a silent duplicate if it ever happens; the fix itself →
  a new story, recorded open in `engineering-findings.yaml` (Task 9).
- A `data_quality_issues` writer for rows the resolver cannot identify → deferred; such rows are
  counted in the stage summary instead (AC 7). Any new writer needs a retraction story first
  (`story_13_3_data_quality_issues_are_write_only`). The dev store has **0** such rows today.
- Declared brands with no filed carrying value (CPB Noosa, Late July — impairment only) get no
  rows; that is the filing's shape, not a gap. 13.4d covers their impairments.
- The live-data DoD override names `data.sec.gov` company-facts, which carries **no dimensions**
  (`company_facts_api_carries_no_segment_dimensions`); verification here runs against the stored
  Inline-XBRL facts plus a live instance spot-check (Task 10). Rewording the override is a process
  fix, not this story's.

## Acceptance Criteria

1. **A derived store with the epic's idempotency key.** A new table `brand_figures`, created by an
   Alembic migration revising `d4f61a2b9c30`, holds one row per
   `(issuer_cik, brand_key, figure, fiscal_year, formula_version, mapping_version)` — a real UNIQUE
   constraint, which is the writer's upsert target. Each row carries `kind` and `source_axis` from
   the resolved identity, `basis`, `value` (`NUMERIC(28,6)`, nullable), `unit`, `period_end`,
   `status` (`ok` | `insufficient_data`), `reason`, `caveats` (JSONB list) and
   `source_member_fact_id`, an FK to the `canonical_member_facts` row the value came from (AD-19:
   provenance reaches the member and its filing through that row).

2. **Materialized on the write path only (AD-1, NFR-8).** `pipeline/run.py::run_issuer` calls the
   new stage after canonicalization and before commit, and its summary reports the count. Nothing on
   the read path computes the series. Stated consequence: **the feature is absent until the pipeline
   runs** — a fresh database has no `brand_figures` rows until the cron (or `make` target) runs.

3. **Idempotent under the daily cron.** Running the stage twice over the same canonical facts leaves
   the same rows: same count, same values, no duplicates. A brand-year that stops resolving under the
   SAME `(formula_version, mapping_version)` is removed on the next run rather than lingering beside
   tonight's set (the `materialize_reverse_dcf` stale-row lesson). Rows under any other version pair
   are never touched.

4. **A versioned spec declares inputs, missing-data policy and rounding, and the inputs list is
   ENFORCED.** `backend/formulas/specs/brand_carrying_value_v1.yaml` loads through
   `formulas.engine.load_spec` and declares: `inputs` (exactly the three canonical concepts read),
   `missing_data_policy: insufficient_data`, a `rounding` block (AD-15; values are filed amounts, so
   quantization at 6 places must be the identity — asserted by a test), the basis table (AC 5) and
   the pre-acquisition rule (AC 8), each with a maintainer `note` and a stand-alone `rationale`.
   The materializer's concept filter is READ FROM `inputs` — not a second list in code — and a test
   proves a `canonical_member_facts` row under an undeclared concept is never read (the
   `piotroski_v1.yaml` defect, where declared and read inputs silently disagreed).

5. **Basis is data, never inferred later.** A row whose context carries no qualifier beyond the
   mapped/brand axes is `basis: carrying_value`. A row qualified by
   `us-gaap:FairValueByMeasurementFrequencyAxis = us-gaap:FairValueMeasurementsNonrecurringMember`
   is `basis: nonrecurring_fair_value`. The mapping from qualifier to basis lives in the spec; a row
   with any qualifier the spec does not declare is `status: insufficient_data` with the qualifier
   named in `reason`, never assigned a basis by guess.

6. **One figure per brand-year, chosen by declared precedence or not at all.** When several source
   rows resolve to the same brand-year, `carrying_value` basis beats `nonrecurring_fair_value` (order
   declared in the spec). Two rows of the SAME winning basis with different values →
   `status: insufficient_data`, `value` NULL, reason naming both source row ids. Never a pick, never
   a sum (AD-3's spirit; AD-16).

7. **Identity comes from 13.4a, under the version it was computed with.** Every row is resolved with
   `resolve_brand_identity(issuer_cik, member_key, context_key)`. Only current
   (`NOT superseded`) rows stamped with the running `MAPPING_VERSION` are read, so the identity and
   the facts come from the same spec version — this closes `deferred_version_blind_resolution` for
   materialized figures. A row that resolves to `BrandUnresolved` writes nothing and increments an
   `unresolved` count in the summary; the dev store must report **0**.

8. **The pre-acquisition comparative zero is annotated, not altered (D-c).** A filed value of exactly
   0 in a brand's earliest materialized fiscal year, followed by a later year with a value > 0, is
   stored as filed (`value: 0`, `status: ok`) with caveat `pre_acquisition_comparative`. The rule is
   in the spec, labelled as ThesisTrace's (the Cameco rule: a presentation guard is ours and says
   so). Live instances: CPB Rao's FY2023, QSR Firehouse Subs FY2020. A zero anywhere else is NOT
   caveated by this rule.

9. **Residual and total are separate series, never summed into the per-brand one.** Rows from
   `brand_intangible_carrying_value_residual` and `brand_intangible_carrying_value_total` are
   materialized under their own `brand_key` and `kind` (`residual`, `aggregate`) exactly as filed.
   No code path adds named-brand values to produce a total or a residual. Test: CPB FY2021's stored
   total is the filed **2,549m**, while the named brands plus the residual sum to **2,867m** — the
   overshoot that disproved summing (us-gaap_v16).

10. **The dev store materializes exactly the expected set.** Against the dev store at
    `concepts_v19`: **86** rows — 67 `named_brand` (CPB 37, QSR 30), 14 `aggregate` (ZTS 8,
    CPB total 6), 5 `residual` (CPB); exactly **2** `nonrecurring_fair_value` rows (CPB Allied
    Brands, Pop Secret FY2024); exactly **2** `pre_acquisition_comparative` caveats; **0**
    `insufficient_data`; **0** unresolved. Every row's value equals its source row's value.

## Tasks / Subtasks

- [x] **1. Amend the epic AC (overtaken by events).** In `epics.md` Story 13.4c, replace "WRITES INTO
      it and must not redefine its table…" with the D-a wording (derived `brand_figures` table; the
      member store stays canonical-only and unchanged). Keep the `### Story 13.4c` heading byte-for-byte
      (story keys are derived from it). (AC 1)
- [x] **2. Migration + model.** Alembic revision on `d4f61a2b9c30` creating `brand_figures` with the
      UNIQUE constraint `uq_brand_figures_key` and indexes on `issuer_cik`, `brand_key`; `BrandFigure`
      in `app/models.py`. Downgrade drops the table (derived and fully recomputable — unlike the
      canonical stores, it holds no append-only history). Run `make migrate` against dev. (AC 1)
- [x] **3. Spec.** `brand_carrying_value_v1.yaml`: `model`, `formula_version`, `inputs`,
      `missing_data_policy`, `rounding`, `basis_qualifiers` + `basis_precedence`, `pre_acquisition`
      rule, each with `note` and `rationale`. A load-time check rejects a spec whose `inputs` is
      empty, or whose basis table names a qualifier axis no dimensioned rule context can carry. Do
      NOT add it to `MODEL_TO_SPEC` (no methodology publication in this story). (AC 4, 5, 6, 8)
- [x] **4. Materializer.** New module `backend/brands/store.py` (sibling of `valuation/store.py`):
      `materialize_brand_carrying_values(session, issuer_cik) -> dict` reading current-version rows
      for the spec's `inputs`, resolving identity, assigning basis, applying precedence and the
      pre-acquisition rule, upserting on `uq_brand_figures_key` (refresh every non-key column, as
      `materialize_reverse_dcf` does), then deleting this issuer's rows under the same version pair
      that tonight's run did not produce. Values pass through `formulas.engine` (`to_decimal`,
      quantize per spec). Returns `{"written", "removed", "unresolved", "insufficient"}`.
      (AC 2, 3, 5-9)
- [x] **5. Wire it.** Call it in `run_issuer` after `materialize_reverse_dcf`, before `commit`; add
      the summary to the return dict and to `main()`'s `OK` line. Add a `make` target
      (`make brands`, `##` comment) that materializes every issuer from stored facts with no network
      fetch, for the dev store and post-deploy. (AC 2)
- [x] **6. Tests** (`backend/tests/test_brand_figures.py`, DB-backed with `requires_db`; seed real
      `canonical_member_facts` rows; **assert the row COUNT before asserting anything about rows**):
  - [x] idempotency: run twice → same count/values; a source row superseded without replacement →
        its brand-year removed on rerun; a row under another version pair untouched. (AC 3)
  - [x] inputs enforced: a seeded row under an undeclared concept is not read; removing a concept
        from a temp copy of the spec stops it being read (the code follows the spec). (AC 4)
  - [x] rounding is the identity on a filed value with 6 decimals. (AC 4)
  - [x] basis: unqualified → `carrying_value`; nonrecurring FV → `nonrecurring_fair_value`; unknown
        qualifier → `insufficient_data` naming it. (AC 5)
  - [x] precedence: carrying beats FV for one brand-year; two disagreeing carrying rows →
        `insufficient_data`, NULL value, both ids in reason. (AC 6)
  - [x] identity: QSR segment rows land under `burger_king`/`tim_hortons`/… not `trade_names`; an
        unresolvable row writes nothing and counts 1 unresolved; a row stamped with an older
        `mapping_version` is not read. (AC 7)
  - [x] pre-acquisition: 0-then-positive → caveat; a 0 in a later year → no caveat; 0 with no later
        positive → no caveat. (AC 8)
  - [x] no summing: CPB FY2021 total stored as 2,549m while brands + residual = 2,867m. (AC 9)
  - [x] wiring: `run_issuer` over a fixture with member facts writes `brand_figures` rows (asserts a
        nonzero count — the 13.4a vacuous-test lesson). (AC 2)
- [x] **7. Mutation audit.** COMMIT FIRST (`never_run_a_mutation_harness_on_uncommitted_work`), then
      break each guarantee in memory and confirm the paired test fails ON AN ASSERTION, not an import:
      precedence, basis-from-spec, inputs-from-spec, stale-row deletion, pre-acquisition rule,
      version filter. Record results in Completion Notes; reuse the shape of
      `scripts/verify_exclusion_guards.py` (PR #154) if a script is warranted.
- [x] **8. Dev-store run.** `make migrate`, then `make brands`; check AC 10's exact counts with a query
      saved under `scripts/` or the scratchpad, run by `make py F=`. Run it twice and confirm the
      second run writes the same 86 rows and removes 0. (AC 3, 10)
- [x] **9. Record.** `engineering-findings.yaml`: a `story_13_4c_brand_carrying_value_materialized`
      entry (counts, the two basis rows, the two caveats, the spot-check result); mark
      `deferred_version_blind_resolution` closed-for-materialized-figures; record
      `deferred_the_segment_rename_exposure` as open with its new home (a new story).
- [x] **10. Live-data DoD.**
  - [x] (1) Check `engineering-findings.yaml` first: `story_13_3_brand_member_live_verification`
        and `story_13_3_multi_axis_member_identity_verified` already live-verified every member and
        year these rows come from. Do not re-fetch what they answered.
  - [x] (2) Per-year coverage: company-facts carries no dimensions, so verify against the stored
        Inline-XBRL `raw_facts` (AC 10's counts, bucketed on `period_end`, not `fy`), plus a live
        spot-check of **two** instance documents, named here and asked for in ONE request before
        fetching: **CPB** (CIK `0000016732`) accession `0000016732-24-000130` — Rao's FY2024 = 1,470m
        and Pop Secret FY2024 = 28m nonrecurring FV; **QSR** (CIK `0001618756`) accession
        `0001618756-22-000018` — Firehouse Subs FY2021 = 768m and FY2020 = 0.
  - [x] (3) Before calling any gap a defect, grep `us-gaap_v18.yaml` for the concept and read its
        `note` (e.g. Noosa/Late July having no carrying rows is the filing's shape).
  - [x] (4) Golden fixture: N/A this story — the harness cannot express a member
        (`golden_harness_cannot_reach_dimensioned_member_facts`); entries → 13.6a/13.6b. Say so.
  - [x] (5) Browser render: N/A — this story renders nothing; no API or page reads `brand_figures`
        yet. State it in Completion Notes; 13.7b/13.8a carry the render.
  - [x] (6) Record the verification (Task 9).
  - [x] (7) Triage every finding: BLOCKING only if it contradicts an AC above or a wrong figure is
        user-visible (none can be — nothing renders). Everything else → a new story, and this one
        merges.
- [x] **11. Close.** `make test` green, `make lint` clean; story → `review`, sprint-status
      `13-4c-…: review`; commit, push, open the PR, hand over a Codex review prompt. Do not merge.

## Dev Notes

### Current state — what exists

- **`canonical_member_facts`** (`app/models.py:210`, migrations `e91b7c4d2a05`, `d4f61a2b9c30`):
  filed per-member values, unique on
  `(issuer_cik, canonical_concept, member_key, fiscal_year, mapping_version, context_key)` WHERE NOT
  superseded. `context_key` = `dimensions` with the mapped axis's alias replaced by `member_key`.
  Written only by `canonicalize_issuer`. **Read-only to this story.**
- **`resolve_brand_identity`** (`canonicalization/mappings/brand_identity.py:127`): returns
  `BrandIdentity(issuer_cik, brand_key, label, kind, source_axis)` or a FALSY `BrandUnresolved`.
  Read-time only and resolves against the CURRENT spec — which is why AC 7 reads only rows at the
  running `MAPPING_VERSION`. It already ignores qualifier axes for identity (CPB's FV-qualified
  rows resolve to the same brand as unqualified ones); BASIS (AC 5) is this story's job, not the
  resolver's. Do not add basis logic to the resolver.
- **Formula engine** (`formulas/engine.py`): `load_spec` (cached), `to_decimal`, `round_ratio`.
  `load_spec` reads `model`, `formula_version`, `rounding`, `missing_data_policy`; everything else is
  in `.raw`.
- **Write-path precedent** (`valuation/store.py:64`): `pg_insert(...).on_conflict_do_update` on a
  named constraint, refreshing every non-key column, then deleting stale rows. Mirror it.
- **Inputs enforcement precedent**: `tests/test_methodology_publication.py:23` and
  `tests/test_rewards_risks.py:303`.
- **Methodology publication** is by explicit `MODEL_TO_SPEC`, not a directory glob — a new spec file
  is not published unless added there. Leave it out.

### The live data (dev store, `concepts_v19`, queried 2026-10-08)

| Filer | Concept | Rows | Members/brands | Years |
|---|---|---|---|---|
| CPB | `brand_intangible_carrying_value` | 37 | 9 named brands | FY2020-25 |
| CPB | `..._residual` | 5 | `other_trade_names` | FY2021-25 |
| CPB | `..._total` | 6 | `all_trademarks` | FY2020-25 |
| QSR | `brand_intangible_carrying_value` | 30 | 1 member (`trade_names`) → 4 segment brands | FY2018-25 |
| ZTS | `brand_intangible_carrying_value` | 8 | `brands` (kind `aggregate`) | FY2018-25 |

Every brand-year has exactly ONE row today (no precedence conflict is live; AC 6 is a guard).
- CPB Allied Brands (43m) and Pop Secret (28m), FY2024, period_end 2024-07-28: ONLY in context
  `{FairValueByMeasurementFrequencyAxis: FairValueMeasurementsNonrecurringMember}` — the post-
  impairment remeasurement (impairments 53m / 76m that year). → `nonrecurring_fair_value` (D-b).
- CPB Rao's FY2023 = 0 (comparative in `0000016732-24-000130`; Sovos closed March 2024) and QSR
  Firehouse FY2020 = 0 (comparative in `0001618756-22-000018`; closed December 2021). → D-c caveat.
- CPB Snyder's of Hanover 620m → 470m in FY2025: the 150m impairment. A real movement; nothing to
  flag here (13.4d stores the impairment).
- ZTS has NO named brand: its only member is the aggregate "Brands". Its series is `kind: aggregate`
  and must never be presented as a brand (13.7b's concern; this story just records `kind`).

### Architecture compliance

- **AD-1 / NFR-8:** compute on write, read never computes. **AD-5 / AD-15 / NFR-2:** shared decimal
  engine, NUMERIC storage, rounding declared in the spec. **AD-16:** tri-state; no defaulted value;
  an ambiguous brand-year is `insufficient_data`, not a pick. **AD-19:** every row FKs its source
  member fact. **AD-2:** `mapping_version` + `formula_version` in the key, so a spec bump writes new
  rows rather than rewriting old ones.
- **Never add a writer to the batch pipeline without an idempotency key** (project-context
  anti-pattern) — AC 3 is that key, and its stale-row half.
- **The conformance rule:** every declaration in the new spec must be read by the code or rejected by
  the loader. `basis_precedence` and `pre_acquisition` are read; `inputs` drives the query.

### File structure

- NEW `db/migrations/versions/<rev>_add_brand_figures.py`
- NEW `backend/brands/__init__.py`, `backend/brands/store.py`
- NEW `backend/formulas/specs/brand_carrying_value_v1.yaml`
- NEW `backend/tests/test_brand_figures.py`
- UPDATE `backend/app/models.py` (`BrandFigure`), `backend/pipeline/run.py` (one call + summary),
  `Makefile` (`brands` target), `_bmad-output/planning-artifacts/epics.md` (AC wording only),
  `_bmad-output/implementation-artifacts/engineering-findings.yaml`, `sprint-status.yaml`.
- Preserve in `run.py`: stage order (ingest → canonicalize → validate → score → reverse DCF), the
  single `commit`, and the existing return keys.

### Testing standards

`make test` only (it guards the shared test DB). DB tests use `requires_db` and the `db_session`
fixture; seed `Issuer`, `Filing`, `RawFact` and `CanonicalMemberFact` like
`tests/test_member_canonicalization.py`. Assert counts before contents. Mutation-verify after
committing (Task 7).

### Previous-story intelligence (13.4a, 13.4b, PR #154)

- A vacuous DB test passes a mutation audit — seed, then assert the count.
- A validator that compares declarations only to each other cannot catch a consistent mistake;
  Task 3's qualifier-axis check compares against `DIMENSIONED_RULES`.
- Never run a mutation harness on uncommitted work.
- Codex reliably finds 2-4 real issues per round and has, in the past, flipped status to `done`;
  re-check `sprint-status.yaml` after any review round.
- PR #154 (13.4b review fixes) is open and touches only the exclusion index in `engine.py` and
  tests. No overlap with this story's files; rebase onto `main` if it merges first.

### Project context reference

`.claude/context/project-context.md` — especially the Epic 6 learnings (write-path moves make a
feature absent until the pipeline runs; NUMERIC scale vs algorithm), the conformance rule, and the
2026-10-07/08 learnings (vacuous tests, empty results that read as "no issues").

## Dev Agent Record

### Agent Model Used

Claude Opus 5.5 (`claude-opus-5-5`), via `bmad-dev-story` (BMad 6.12.1 shim).

### Debug Log References

- `make brands` (dev store, `concepts_v19`), run twice: CPB 48 / QSR 30 / ZTS 8 written, 0 removed,
  0 unresolved, 0 insufficient — identical both runs.
- `make py F=scripts/verify_brand_figure_guards.py`: all 9 mutations killed, 12 call-phase
  `AssertionError`s, 0 skips, 0 collection/setup errors.
- `make py F=scripts/spot_check_brand_figures.py`: 4/4 live values match, each matched by exactly
  one filed fact.

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- **AC 1-3.** `brand_figures` (migration `f3a8c2d61b47`, model `BrandFigure`) with UNIQUE
  `uq_brand_figures_key` and a CHECK that a row is either `ok` with a value or `insufficient_data`
  with no value and a reason. `materialize_brand_carrying_values` upserts on the key, then deletes
  this issuer's rows under the same version pair that the run did not write. Wired into
  `run_issuer` after the reverse DCF; summary in the return dict and `main()`'s `OK` line;
  `make brands` materializes from stored facts with no fetch. Feature is absent until it runs.
- **AC 4.** `brand_carrying_value_v1.yaml`; the query's concept filter IS `spec.inputs`. Rounding
  through `formulas.engine.round_ratio` at 6 places, asserted to be the identity on filed amounts.
- **AC 5-6.** Basis from the context's non-identity axes. An undeclared qualifier makes the WHOLE
  brand-year `insufficient_data`, naming it — even beside a declared row (changed in the Codex
  round, F1; round 1 let the declared row win).
  Precedence from the spec; two disagreeing rows of the winning basis → `insufficient_data`, NULL
  value, both ids in `reason`; equal values collapse to one figure.
- **AC 7.** Identity via `resolve_brand_identity`; only `NOT superseded` rows at the running
  `MAPPING_VERSION` are read. Unresolved rows write nothing and are counted (dev store: 0).
- **AC 8-9.** Pre-acquisition rule as specified; residual/total materialized as their own series.
- **AC 10.** Exact: 86 rows (67 named, 14 aggregate, 5 residual), 2 `nonrecurring_fair_value`, 2
  `pre_acquisition_comparative`, 0 insufficient, 0 unresolved, 0 value mismatches vs source rows,
  0 rows without `source_member_fact_id`.
- **Deviation 1 (Task 3).** The planned loader check "a qualifier axis no dimensioned rule context
  can carry" has nothing executed to compare against — `DIMENSIONED_RULES` declare mapped axes
  only. Implemented the checks that do compare against executed declarations instead: a basis
  qualifier must NOT be an identity axis (from `DIMENSIONED_RULES`, segment and brand axes), and
  every input must be a concept some dimensioned rule produces. Also rejected: empty inputs, a
  precedence list that does not order every declared basis once, a caveat no code applies.
- **Deviation 2 (Task 6, wiring).** The only `run_issuer` fixture is SHOP, which declares no
  brands, so the wiring test spies on the stage call and asserts its summary surfaces; the
  DB-backed store tests are what prove rows land (each asserts a nonzero count first).
- **The mutation audit found a real test defect**: the "other version pair untouched" test seeded
  its foreign-version row at the same brand-year the run writes, so it passed with the version
  scope removed. Fixed (`76f0d0c`); recorded in `engineering-findings.yaml`.
- **Live-data DoD.** (1) checked findings first — the 13.3 live verifications cover every member
  and year; (2) coverage verified against the stored Inline-XBRL facts (AC 10) plus the live spot
  check of CPB `0000016732-24-000130` and QSR `0001618756-22-000018`; (3) the gaps seen (Noosa and
  Late July have no carrying rows) are the filing's shape per the spec notes; (4) golden fixtures:
  N/A, the harness cannot express a member (→ 13.6a/b); (5) browser render: N/A — nothing reads
  `brand_figures` yet, no API or page changed (→ 13.7b/13.8a); (6) recorded as
  `story_13_4c_brand_carrying_value_materialized`; (7) triage: no finding contradicts an AC and
  nothing is user-visible, so nothing blocks. Deferred: the segment-rename exposure → a new story.
- `make test`: 595 passed. `make lint`: clean.

#### Codex review round (2026-10-08, commits `21667e0` tests, `5f2a40d` fix)

Five findings, each reproduced by a test committed BEFORE the fix and seen red. Verified
independently afterwards: `make test` 621 passed, lint clean, audit 9/9 required + 9/9
supplemental mutations killed on `AssertionError`, and `make brands` on the dev store still
writes the same 86 rows (2 fair-value, 2 caveats, 0 insufficient, 0 removed).
- **F1 (AC 5, rule change).** An undeclared qualifier now vetoes the whole brand-year instead of
  being dropped beside a declared sibling. Round 1's behaviour was a deliberate choice, not an
  oversight, but it read AC 5 at row level; brand-year level is the stricter AD-16 reading — an
  unexplained measurement of the same brand-year is not hidden behind the winner. No live row
  changes (0 such contexts in the dev store).
- **F2 (AC 8, bug).** Round 1 counted only RESOLVED years when finding a brand's earliest year,
  so an insufficient first year moved the pre-acquisition caveat onto a later zero. Fixed:
  every materialized year establishes the series start.
- **F3.** `computed_at` was not refreshed on upsert. **F4.** The loader accepted a
  `missing_data_policy` no code implements. **F5.** The wiring test was a spy; it is now a real
  offline CPB pipeline run asserting 18 committed figures, plus fractional-amount and
  scoped-deletion tests and nine supplemental mutations.
- New: `backend/tests/test_brand_figure_migration.py` — Alembic round-trip of the real migration
  on the guarded test DB; filed member facts survive; model and migration enforce the same CHECK.

### Change Log

- 2026-10-08 — Story file created; decisions D-a..D-d taken with Lawrence before drafting.
- 2026-10-08 — Implemented: `brand_figures` store, `brand_carrying_value_v1` spec, write-path stage,
  `make brands`, tests, mutation audit, live spot-check; epic AC corrected. No existing figure changed.
- 2026-10-08 — Codex review round: F1-F5 fixed (unknown-qualifier veto, caveat start year,
  `computed_at` refresh, policy check, real pipeline/migration tests). Dev-store output unchanged.

### File List

- `db/migrations/versions/f3a8c2d61b47_add_brand_figures.py` (new)
- `backend/app/models.py`
- `backend/brands/__init__.py` (new)
- `backend/brands/__main__.py` (new)
- `backend/brands/store.py` (new)
- `backend/formulas/specs/brand_carrying_value_v1.yaml` (new)
- `backend/pipeline/run.py`
- `backend/tests/test_brand_figures.py` (new)
- `backend/tests/test_brand_figure_migration.py` (new, Codex round)
- `backend/tests/test_sprint_status.py`
- `scripts/verify_brand_figure_guards.py` (new)
- `scripts/spot_check_brand_figures.py` (new)
- `Makefile`
- `_bmad-output/planning-artifacts/epics.md`
- `_bmad-output/implementation-artifacts/engineering-findings.yaml`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/13-4c-per-brand-carrying-value-computed-and-materialized.md`
