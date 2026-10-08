---
baseline_commit: b882f658d2f82bf4a95c93680b6ac75f9ff50575
---

# Story 13.4b: An exclusion says which axis it speaks for

Status: review

## Story

As Lawrence (developer),
I want `excluded_members` scoped to the axis it was verified against, and unreachable exclusions
rejected at load,
so that a recorded decision keeps suppressing exactly what it ruled on, and an exclusion that can
never fire is caught instead of reading like an enforced one.

## Scope boundary (read first)

**One outcome: an exclusion's reach equals the evidence behind it.** This story changes the shape
of `excluded_members`, the check that loads it, and the one predicate canonicalization uses to stay
silent. It moves **no figure**: exclusions decide only whether an `unmapped_member` data-quality
row is written, never which value lands in `canonical_member_facts`.

**Out of scope / deferred** (each has a home):
- Should an exclusion also be able to withhold a *mapped* member on one axis while it resolves on
  another? → not this story. `_check_exclusions` keeps rejecting mapped-and-excluded outright; no
  filer needs the split today, and allowing it is a new capability, not a scoping fix.
- Version-blind identity resolution (`deferred_version_blind_resolution`, Codex on 13.4a) → 13.4c.
- The segment-rename exposure (`_dimension_identity` does not normalize the segment axis) →
  recorded open by 13.4a, belongs with 13.4c or its own story.
- `data_quality_issues` carry no `mapping_version` and cannot be retracted
  (`story_13_3_data_quality_issues_are_write_only`) → not touched here. The dev store holds **0**
  `unmapped_member` rows today, so this story has nothing to retract.
- Golden entries → 13.6a/13.6b; the harness cannot express a dimensioned fact yet.
- The live-data DoD override (`_bmad/custom/bmad-create-story.toml`) names `data.sec.gov`
  company-facts, which carries **no dimensions** (`company_facts_api_carries_no_segment_dimensions`).
  This story verifies against the dev store's Inline-XBRL `raw_facts` instead (see Dev Notes
  "Definition of Done"). Rewording the override is a process fix, not this story's.

## Acceptance Criteria

1. **An exclusion declares the axis it was verified against.** Every `excluded_members` entry
   carries a required `axis`, and optionally `source_concepts` (the source concepts it was observed
   on). An entry with no `axis` is rejected at load, naming the member.

2. **Suppression keys on the full resolution identity.** Canonicalization stays silent about an
   unresolved dimensioned fact only when an exclusion for that **issuer** names its **axis** and
   its **member as filed** — and, where the exclusion declares `source_concepts`, its **source
   concept**. The same member on any other axis or concept is flagged as `unmapped_member` exactly
   as an unknown member would be. Today `canonicalize.py:727` keys on `(issuer, member)` alone.

3. **An unreachable exclusion is rejected at load, with its member named.** An exclusion is
   reachable only if at least one dimensioned rule applicable to that issuer (`issuers` empty, or
   containing it) reads the exclusion's axis — and, if it declares `source_concepts`, reads each of
   those concepts on that axis. Reachability is checked against `DIMENSIONED_RULES` (something the
   pipeline actually executes), never against another declaration in the same file — the lesson of
   `validated_against_a_declaration_is_not_validated` (13.4a round 2).

4. **The shipped spec loads under the new rule, with every surviving exclusion grounded.** The new
   spec declares, for each exclusion it keeps, the axis and source concept on which the dev store's
   real filings carry it (Dev Notes "The live data"). Of the nine exclusions in `us-gaap_v17`, only
   **two** are reachable (ZTS `in_process_rnd`, `product_rights`); the other **seven** are tagged
   only on `us-gaap:FiniteLivedIntangibleAssetsByMajorClassAxis` or not at all, and are disposed of
   per Dev Notes "Decision — the seven inert exclusions". None is re-declared on an axis it was not
   observed on.

5. **The spec version is bumped, not amended.** `us-gaap_v18.yaml` behind `concepts_v19`, with a
   registry HISTORY entry stating this version changes no figure. Re-canonicalizing the dev store
   under `concepts_v19` reproduces `concepts_v18`'s 96 current rows IDENTICALLY, and writes **0**
   `unmapped_member` rows (baseline: 0).

6. **Tests fail before the fix.** Each of these was seen red against the pre-change code, recorded
   in Completion Notes:
   - wrong axis: an exclusion verified on axis A does not suppress the same member on a mapped
     axis B (AC 2);
   - wrong concept: an exclusion with `source_concepts` does not suppress the member on another
     mapped concept on the same axis (AC 2);
   - unreachable: an exclusion on an axis no applicable rule reads is rejected, message naming the
     member (AC 3) — including one whose axis IS read, but only by a rule scoped to a different
     issuer;
   - missing axis rejected (AC 1).
   The existing `test_an_excluded_member_is_withheld_without_a_warning` and
   `test_an_exclusion_is_scoped_to_its_own_filer` stay green unchanged.

## Tasks / Subtasks

- [x] **1. Decide the seven inert exclusions** (AC: 4) — **done 2026-10-08: A, remove.** See Dev Notes "Decision".
- [x] **2. Make suppression a pure, testable predicate** (AC: 2)
  - [x] Add `axis: str` and `source_concepts: tuple[str, ...] = ()` to `ExcludedMember`
        (`mappings/engine.py:191`); `_load_excluded_members` reads both and rejects a missing
        `axis` (AC 1).
  - [x] Add one lookup built at load — e.g. `EXCLUSION_RESOLUTION` keyed
        `(issuer_cik, axis, member_as_filed)` → the exclusion — and a function
        `is_excluded(issuer_cik, taxonomy, source_concept, axis, member) -> bool` beside it.
  - [x] Replace `excluded_member_aliases` in `canonicalize.py:677-681` and its use at `:727` with
        that function. No other change to `_canonicalize_member_facts`.
- [x] **3. Reject unreachable exclusions at load** (AC: 3)
  - [x] Extend `_check_exclusions` (`engine.py:487`) to take `dimensioned` and apply AC 3, deriving
        the readable `(issuer, axis, source_concept)` set from `DimensionedRule.issuers`/`axis`/
        `source_concept` the same way `_check_brand_identity` derives `rule_axes` (`:638-660`).
  - [x] Keep the existing reason / aliases / mapped-and-excluded checks as they are.
  - [x] Update the call in `load_mapping_spec` (`:788`).
- [x] **4. New spec version** (AC: 4, 5)
  - [x] Copy `us-gaap_v17.yaml` → `us-gaap_v18.yaml`; never edit v17.
  - [x] Add `axis: us-gaap:IndefiniteLivedIntangibleAssetsByMajorClassAxis` and
        `source_concepts: [IndefiniteLivedIntangibleAssetsExcludingGoodwill]` to ZTS
        `in_process_rnd` and `product_rights`; extend each `reason` with the axis, concept and
        years observed (14 rows each, FY2018-FY2025).
  - [x] Apply the Task 1 decision to the other seven.
  - [x] Point `registry.yaml` at `us-gaap_v18` under `mapping_version: concepts_v19`, HISTORY entry
        stating no figure changes.
- [x] **5. Tests** (AC: 6)
  - [x] Unit tests in `backend/tests/test_brand_member_mapping.py`, beside
        `test_a_member_cannot_be_both_mapped_and_excluded`: wrong axis, wrong concept, unreachable
        (both shapes), missing axis. Construct `ExcludedMember` / `DimensionedRule` values
        directly; do not read the spec to assert the spec.
  - [x] Update `test_every_exclusion_states_why_and_is_not_also_mapped` (`test_brand_member_mapping.py:344`) so it
        also asserts every shipped exclusion's axis is read by a rule for its issuer — and **assert
        the count (2) before the loop**, so an emptied list fails instead of passing.
  - [x] Run each new test against the pre-change code first and record that it was red.
- [x] **6. Re-canonicalize under `concepts_v19`** (AC: 5)
  - [x] `make py F=scripts/recanonicalize.py` against the dev DB; confirm `concepts_v18` vs
        `concepts_v19` IDENTICAL (96 rows) and 0 `unmapped_member` rows written.
- [x] **7. Live-data DoD**
  - [x] (1) Check `engineering-findings.yaml` for an existing answer — done at story creation:
        `story_13_3_member_exclusions_are_not_axis_scoped` (the finding this story closes) and
        `story_13_3_zts_non_brand_intangibles_land_as_brand_value` (why the ZTS two exist).
  - [x] (2) Verify per-year coverage — for dimensioned facts this means the dev store's
        Inline-XBRL `raw_facts`, not `data.sec.gov` company-facts (which carries no dimensions).
        Re-run the Dev Notes query for CPB 0000016732, ZTS 0001555280, QSR 0001618756 and confirm
        it still matches the table; bucket on `period_end`, not EDGAR `fy`. No live fetch is
        expected; if one becomes necessary, ask for all three CIKs in one message first.
  - [x] (3) Grep each removed or rescoped exclusion's `reason` before changing it (done in Dev
        Notes; re-check if the spec moved).
  - [x] (4) Golden fixtures: confirm none is needed — 13.6a/13.6b own dimensioned golden entries.
  - [x] (5) Render `/company/ZTS`, `/company/QSR` and `/company/CPB` (`make api` :8001 +
        `make web` :3001) after the re-canonicalize and confirm the data-quality section shows **no**
        `unmapped_member` warning. Subjects by code path: ZTS exercises a SURVIVING exclusion (if
        axis-scoping broke suppression, its 28 IPR&D/product-rights rows would surface as
        warnings); QSR exercises REMOVED exclusions on an unread axis; CPB exercises a removed
        exclusion beside a fully mapped filer.
  - [x] (6) Record the verification in `engineering-findings.yaml`: set
        `story_13_3_member_exclusions_are_not_axis_scoped` to `done` with the evidence, and note
        that the finding undercounted (3 inert named, 7 actual).
  - [x] (7) Triage anything the verification finds as blocking vs deferred (CLAUDE.md story
        workflow rule 3).
- [x] **8. Close out**
  - [x] `make test` green, `make lint` clean.
  - [x] Commit, push, open the PR, hand over a Codex review prompt. Do not merge.

## Dev Notes

### Current state — what exists

- `ExcludedMember(issuer_cik, member_key, aliases, reason)` — `mappings/engine.py:191`. No axis.
- `_check_exclusions(members, excluded)` — `engine.py:487`. Rejects a missing reason, missing
  aliases, and an alias both mapped and excluded. **Never checks reachability.**
- `_check_brand_identity` — `engine.py:519`. Also reads `excluded` (alias collisions with segment
  brands, `:573-608`) and already derives readable axes per issuer from `DIMENSIONED_RULES`
  (`:638-660`) — **the pattern Task 3 reuses.** Leave its exclusion-collision check as is.
- `canonicalize.py:677-681` builds `excluded_member_aliases = {(issuer, alias)}`; `:726-730` flags
  an unresolved fact only if `(issuer, member)` is not in that set **and**
  `(taxonomy, concept, axis)` is an applicable rule source. So a fact on an *unread* axis is never
  flagged whatever the exclusions say — which is exactly why the seven below are inert, and why the
  wrong-axis exposure is invisible today: every dimensioned rule reads ONE axis.
- Every dimensioned concept in `us-gaap_v17` reads
  `us-gaap:IndefiniteLivedIntangibleAssetsByMajorClassAxis`. Applicable to ZTS and QSR: only
  `brand_intangible_carrying_value` and `trade_names_within_ten_percent_of_impairment`, both on
  `IndefiniteLivedIntangibleAssetsExcludingGoodwill`. The other four are `issuers: [CPB]`.
- `ifrs-full_v4.yaml` declares no `excluded_members`.

### The live data (dev store `raw_facts`, Inline XBRL, queried 2026-10-08)

Every excluded alias, by where its issuer's real filings carry it:

| Issuer | Exclusion | Axis it is tagged on | Concepts | Rows / years | Reachable |
|---|---|---|---|---|---|
| ZTS | `in_process_rnd` | **Indefinite**-lived | `IndefiniteLivedIntangibleAssetsExcludingGoodwill` | 14 / 2018-2025 | **yes** |
| ZTS | `product_rights` | **Indefinite**-lived | `IndefiniteLivedIntangibleAssetsExcludingGoodwill` | 14 / 2018-2025 | **yes** |
| ZTS | `developed_technology` | Finite-lived | Gross / AccumAmort / Net, one acquisition fact | 43 / 2018-2025 | no |
| ZTS | `other_intangibles` | Finite-lived | Gross / AccumAmort / Net, one acquisition fact | 43 / 2018-2025 | no |
| ZTS | `customer_relationships` | — not tagged at all — | — | 0 | no |
| CPB | `customer_relationships` | Finite-lived | Gross / AccumAmort / Net, impairment, disposal | 48 / 2019-2025 | no |
| QSR | `franchise_rights` | Finite-lived | Gross / AccumAmort / Net, acquisition | 45 / 2017-2025 | no |
| QSR | `franchise_agreements` | Finite-lived | Gross / AccumAmort / Net | 12 / 2023-2025 | no |
| QSR | `favorable_leases` | Finite-lived | Gross / AccumAmort / Net, acquisition | 31 / 2017-2025 | no |

Query (re-run for DoD item 2): `raw_facts` joined to `filings`, `jsonb_each_text(dimensions)`
filtered to `jsonb_typeof(dimensions) = 'object'`, grouped by issuer, member, axis, concept, with
min/max `period_end` year. The finding named three inert exclusions; it is seven. Not a new
finding — AC 3 already requires rejecting all of them; the count was simply never taken.

Baseline: **0** `unmapped_member` rows in `data_quality_issues`; current `canonical_member_facts`
under `concepts_v18`: **96**.

### Decision — the seven inert exclusions (Lawrence, 2026-10-08: **A, remove them**)

AC 3 rejects all seven at load, so the spec must change. Options:

- **A. Remove them from `excluded_members` (recommended).** Each suppresses nothing today, and
  re-declaring any of them on the indefinite-lived axis would claim verification on an axis it was
  never observed on — the exact exposure the finding is about. If ZTS ever tags developed
  technology on the indefinite-lived axis, an `unmapped_member` row fires and a human decides with
  the fact in front of them, which is the guard working. Their reasons survive in git history and
  in the `engineering-findings.yaml` close-out entry (DoD item 6), which lists all seven with this
  table's evidence.
- B. Re-declare them on the indefinite-lived axis as anticipatory exclusions ("not a brand on any
  axis"). Rejected: a claim about an axis nobody checked, and it keeps seven declarations whose
  only effect is hypothetical.
- C. Keep them under their true axis (finite-lived) in a separate, unread section. Rejected: a
  declaration nothing reads is decoration — the conformance rule.

### Constraints that must survive from the parent story (13.4)

- **AD-16** — an unknown member is flagged, never guessed or defaulted. Narrowing suppression can
  only produce MORE flags, never fewer resolved rows.
- **AD-19** — `member_as_filed` and `dimensions` stay verbatim; untouched here.
- **AD-2 / versioning** — a spec is frozen once any database stamps its version: bump, never amend.
- **The conformance rule** — every field this story adds (`axis`, `source_concepts`) must be *read*
  by `is_excluded` or *rejected* by the loader. A `source_concepts` nothing checks would be the
  eighth instance.
- **Idempotency** — `_canonicalize_member_facts` dedups `unmapped_member` writes on
  `(taxonomy, source_concept, axis, member_as_filed, fiscal_year)`; do not change that key.

### Testing

- `make test`; single file `make test-one T=tests/test_brand_member_mapping.py`. Docker: `make db-up`.
- The wrong-axis test needs a SECOND mapped axis, which no shipped spec has — so test the predicate
  and loader with constructed `DimensionedRule` / `ExcludedMember` values. A DB test cannot reach
  the wrong-axis case through the real spec, and one that tried would pass vacuously.
- `ExcludedMember(...)` is constructed directly in `test_brand_member_mapping.py:355,363` and in
  `test_brand_identity.py`. Make `axis` a required dataclass field (no default — a default would
  let a constructed exclusion silently claim an axis), and update those call sites.
- Assert counts before asserting over collections (`a_vacuous_test_can_pass_a_mutation_audit`).
- If running the mutation harness, **commit first** — it restores with `git checkout` and has
  discarded uncommitted work once already.

### Definition of Done

Live-data DoD applies (concept-mapping spec). Item 2 is verified against the dev store's Inline
XBRL `raw_facts` because company-facts carries no dimensions; the rows were ingested from the
filers' own instance documents. Item 5 has a real subject this time — the data-quality section on
the company page — and is not optional.

### Project Structure Notes

- New: `backend/canonicalization/mappings/specs/us-gaap_v18.yaml`.
- Modified: `mappings/engine.py`, `canonicalization/canonicalize.py`, `specs/registry.yaml`,
  `tests/test_brand_member_mapping.py`, `engineering-findings.yaml`, `sprint-status.yaml`.
- **No migration.** If one appears, the scope has crept.
- PR via a fresh `claude/13-4b-…-<date>` branch; never a direct push to `main`.

### References

- `_bmad-output/planning-artifacts/epics.md:1488` — Story 13.4b ACs
- `engineering-findings.yaml:5570` — `story_13_3_member_exclusions_are_not_axis_scoped`
- `engineering-findings.yaml:5684` — `story_13_4a_codex_round_found_four_acs_unmet`
  (validator-against-declaration and vacuous-test lessons)
- `backend/canonicalization/mappings/engine.py:191, 473, 487, 519, 638, 788`
- `backend/canonicalization/canonicalize.py:671-749` — member selection and the unmapped flag
- `backend/canonicalization/mappings/specs/us-gaap_v17.yaml:686` (dimensioned concepts),
  `:1035` (excluded_members)
- `backend/tests/test_member_canonicalization.py:537, 579, 597` — existing exclusion DB tests
- `.claude/context/project-context.md` — 2026-09-17 ("exclusions need to be DATA") and 2026-10-07
  learnings

## Dev Agent Record

### Agent Model Used

Claude Opus 5.5 (`claude-opus-5-5`), via `bmad-dev-story` (BMad 6.12.1 shim).

### Debug Log References

- Red run (old engine, before any implementation): ZTS's IPR&D exclusion suppressed on the
  indefinite-lived, finite-lived and an invented axis alike; `_check_exclusions` accepted an
  exclusion on an axis no rule reads; the spec shipped 9 exclusions. The new test module failed at
  import (API absent).
- First run after implementing: 2 failures, both from a test-helper name collision (`_rule` already
  existed in the file); renamed to `_axis_rule`. No production change.
- First API check of DoD item 5 hit `/companies/...` without the `/api` prefix, returned 404, and
  read as "0 issues". Caught because the zero was suspicious; re-checked on the correct route with
  the key asserted present, plus SHOP (18 open issues) as a positive control.

### Completion Notes List

- Story context created 2026-10-08 under BMad 6.12.1 with the #149 overrides active.
- **Decision A (Lawrence, 2026-10-08):** the seven unreachable exclusions are removed, not
  re-declared on an axis they were never observed on.
- **AC 1** — `ExcludedMember.axis` is required (no dataclass default); `_parse_excluded_members`
  rejects a missing `axis` and a scalar `source_concepts`, naming the member.
- **AC 2** — `is_excluded(issuer, source_concept, axis, member)` over `EXCLUSION_INDEX`
  `(issuer, axis, member as filed)`; `canonicalize.py` uses it in place of the axis-blind
  `(issuer, member)` set. Unmapped-member dedup key unchanged.
- **AC 3** — `_check_exclusions(members, excluded, dimensioned)`: `dimensioned` is required, and an
  exclusion is rejected when no applicable rule (issuer-scoped) reads its axis, or any declared
  source concept on it.
- **AC 4** — `us-gaap_v18` keeps ZTS `in_process_rnd` and `product_rights`, each scoped to the
  indefinite-lived axis and `IndefiniteLivedIntangibleAssetsExcludingGoodwill`, reasons citing
  14 facts FY2018-FY2025. The other seven are gone; the header says why.
- **AC 5** — `concepts_v19`. `scripts/recanonicalize.py`: concepts_v18 vs concepts_v19
  **IDENTICAL**, 96 rows; 0 `unmapped_member` rows before and after.
- **AC 6** — new tests: wrong axis, wrong concept, no-`source_concepts` covers the axis,
  unreachable axis, unreachable via another issuer's rule, unreachable concept, reachable loads,
  missing axis, scalar `source_concepts`; the shipped-spec test asserts exactly 2 exclusions and
  each one's axis/concept before looping. Existing DB tests
  `test_an_excluded_member_is_withheld_without_a_warning` and
  `test_an_exclusion_is_scoped_to_its_own_filer` green and unchanged.
- **Live-data DoD:** (1) findings checked; (2) dev-store tagging re-run after re-canonicalizing,
  matches the Dev Notes table exactly; (3) reasons read before removal; (4) no golden entry needed
  (13.6a/b); (5) ZTS/QSR/CPB rendered on :3001 — no data-quality box, footer `concepts_v19`,
  SHOP control shows its box; (6) `story_13_3_member_exclusions_are_not_axis_scoped` → `done`
  with evidence and the undercount; (7) nothing new to triage.
- `make test`: 572 passed. `make lint`: clean.

### Change Log

- 2026-10-08 — Implemented axis-scoped exclusions and load-time reachability; `us-gaap_v18` /
  `concepts_v19`; seven unreachable exclusions removed. No figure changed.

### File List

- `backend/canonicalization/mappings/engine.py`
- `backend/canonicalization/mappings/__init__.py`
- `backend/canonicalization/canonicalize.py`
- `backend/canonicalization/mappings/specs/us-gaap_v18.yaml` (new)
- `backend/canonicalization/mappings/specs/registry.yaml`
- `backend/tests/test_brand_member_mapping.py`
- `backend/tests/test_brand_identity.py`
- `backend/tests/test_free_cash_flow_concepts.py`
- `_bmad-output/implementation-artifacts/engineering-findings.yaml`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/13-4b-an-exclusion-says-which-axis-it-speaks-for.md`
