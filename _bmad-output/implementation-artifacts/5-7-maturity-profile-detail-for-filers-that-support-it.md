---
baseline_commit: b11fbf59cc9db3c503e75653f28014fd3d91a8cd
---

# Story 5.7: Maturity profile detail for filers that support it

Status: review

*Enrichment, not a metric. Ships after 5.6 and may be deferred indefinitely without blocking the epic.*

## Story

As Lawrence (investor),
I want to see the full year-by-year repayment schedule where a filer actually publishes one,
so that I can distinguish a smooth maturity ladder from a cliff.

## Acceptance Criteria

1. **Given** a filer that publishes a multi-year maturity ladder, **when** its Quality/Health lens renders, **then** the year-by-year profile appears as supplementary detail **beneath** the near-term debt share card.

2. **Given** a filer with no ladder, **when** the lens renders, **then** there is **no gap, blank, placeholder, or "missing"/`insufficient_data` affordance of any kind** — the section is simply absent. Five of seven filers structurally cannot have this data; rendering it as missing would misrepresent them as deficient. This is a deliberate exception to the AD-16 display convention (see Dev Notes → *The AD-16 trap*).

3. **Given** a fiscal year whose "thereafter" bucket is absent, **when** the profile renders, **then** it states the schedule is **truncated** rather than implying the displayed buckets are the whole debt. CP FY2010–2021 is this case and the gap is not cosmetic: FY2021's buckets sum to 7,376M against a filed total debt of 20,127M — 63% of the debt is not shown.

4. **Given** any rendered profile, **when** it is displayed, **then** it is **never** presented as reconciling to `total_debt`, and **no bucket is expressed as a percentage of total debt**. The ladder is undiscounted contractual principal; `total_debt` is balance-sheet carrying amount. Verified 2026-08-05 that even a *complete* ladder does not reconcile: QSR FY2023 sums to 13,043M vs a filed total of 12,921M; CP FY2023 sums to 23,133M vs 22,494M.

5. **Given** the profile and the near-term debt share are shown together, **when** both render, **then** the profile's first bucket is **never** presented as the same figure as the near-term share, and the two are visually distinct enough that a reader does not read one as a breakdown of the other. They differ in 11 of 15 shared years for CP and 10 of 10 for OTEX (Story 5.6 finding).

6. **Given** each displayed bucket, **when** it renders, **then** it resolves to provenance — accession number, XBRL concept, fiscal year (AD-19). A value with no resolvable provenance is not displayed as fact.

7. **Given** the new canonical concepts, **when** they are added, **then** per-year coverage is verified **live** against `data.sec.gov`, not inferred from tag presence, and `MAPPING_VERSION` is bumped per `registry.yaml`'s procedure.

8. **Given** the golden dataset, **when** this story ships, **then** `phase1_golden.yaml` is extended in the **same change** for every filer-year the profile resolves for, since SM-1 is a claim about the universe.

9. **Given** the existing guard `test_maturity_ladder_tags_are_not_mapped`, **when** ladder tags become mapped, **then** that test is **refined, not deleted** — it must still assert the ladder never feeds `near_term_debt` or `total_debt` (see Dev Notes → *The test you will trip over*).

## Tasks / Subtasks

- [x] **Task 1 — Live-verify ladder coverage** (AC: 7)
  - [x] Fetch company-facts for all 7 filers; the cached payloads from Story 5.6 are in the session scratchpad, otherwise re-fetch (**ask Lawrence once, naming every CIK** — standing preference).
  - [x] Confirm per-year coverage of the six ladder buckets, bucketing by `period_end` against each issuer's own FYE, **not** the payload's `fy` field.
  - [x] Confirm the expected shape: QSR full ladder FY2014–2024 (FY2025 missing thereafter), CP years 1–5 FY2010–2025 with thereafter only FY2022–2025, OTEX never tags years 2–5, SHOP/CCJ/BCE/SU none at all.

- [x] **Task 2 — Map the six ladder buckets** (AC: 7, 9)
  - [x] Add `us-gaap_v6.yaml` + `derivations_v4.yaml` if needed; bump registry to `concepts_v7`. **Never edit a spec a stored `mapping_version` points at** (AD-2).
  - [x] New concepts: `debt_maturity_year_1` … `debt_maturity_year_5`, `debt_maturity_thereafter`.
  - [x] `ifrs-full`: map nothing. The IFRS maturity analysis is dimensional and structurally unreachable via company-facts (Story 5.1 finding, still true).
  - [x] Refine `test_maturity_ladder_tags_are_not_mapped` per AC 9.
  - [x] Update `NON_MODEL_CONCEPTS` in `test_concept_mappings.py` — these feed a presentation rule, not a model, so the both-regimes rule does not apply.

- [x] **Task 3 — Profile engine** (AC: 3, 4, 5)
  - [x] Extend `backend/debt/` (do **not** create a parallel module — reuse the existing package).
  - [x] Return an ordered bucket list plus an explicit `truncated: bool` when `thereafter` is absent.
  - [x] A filer-year with no year-2..5 buckets yields **no profile at all** — not an empty list rendered as a profile.
  - [x] `Decimal` throughout, never `float` (AD-15).
  - [x] Spec: extend `near_term_debt_share_v1.yaml` **or** add a sibling `kind: thesistrace_presentation_rule` spec. Either way the basis warning must be a machine-readable field, not a YAML comment (this trap has now recurred three times — D8 `derivations_v2`, 5.5 `trajectory_v1`, and it is called out again here).

- [x] **Task 4 — API** (AC: 1, 6)
  - [x] Add to `CompanyOverviewOut`. One query for all six concepts across all years, then a pure computation — mirror the `near_term_debt_share` pass; **must not** become an N+1 (AD-1).
  - [x] Provenance per bucket (AD-19).

- [x] **Task 5 — UI** (AC: 1, 2, 3, 5)
  - [x] New component under `frontend/app/components/`, rendered beneath `NearTermDebtShareCard`, inside `quality_health` only.
  - [x] Return `null` when there is no profile — no wrapper, no heading, no badge.
  - [x] Truncation notice when `truncated`.
  - [x] Custom visualization only — **no TradingView or off-the-shelf charting** (standing project rule).
  - [x] Theme-aware, and horizontal overflow must scroll inside its own container.

- [x] **Task 6 — Golden + verification** (AC: 8)
  - [x] Extend fixtures with the six tags, reusing **only accessions already present** so existing hand-verified values cannot shift.
  - [x] Extend `phase1_golden.yaml` for QSR FY2023 and CP FY2023 (both active golden years with a complete ladder).
  - [x] Hand-compute independently — **import nothing** from `backend/debt`.
  - [x] Confirm the guard bites by corrupting an expected value.
  - [x] **Render it in a browser.** Mandatory, not diligence — it found 4 real bugs in 5.4 and 1 in 5.6 that tests could not.

## Dev Notes

### The test you will trip over

`backend/tests/test_near_term_debt_share.py::test_maturity_ladder_tags_are_not_mapped` currently asserts these tags are absent from `SOURCE_TO_CANONICAL` **entirely**. This story makes that false.

Do **not** delete it. Its real invariant is *"the ladder must never feed the near-term share"* — the assertion was merely written in the strongest form available at the time, when nothing needed the ladder. Refine it to assert the ladder tags map to neither `near_term_debt` nor `total_debt`. Deleting it would retire a guard that is still protecting a live decision.

### The AD-16 trap — read this before writing the empty state

AD-16 and `EXPERIENCE.md` both say absence is informative and must be **shown, not hidden**: `insufficient_data` gets a `pending`-toned badge and is never coerced away. Every other absent value in this product follows that rule.

**This story is the exception, and AC 2 is deliberate.** The distinction:

- AD-16 governs a **signal inside a model that was attempted**. The absence is informative because it explains why a score did not compute.
- The maturity profile is **supplementary disclosure detail**, not a signal and not part of any score. Five of seven filers cannot produce it for structural reasons — the three IFRS filers because their maturity analysis is dimensional and unreachable through company-facts, SHOP because it has no debt ladder, OTEX because it never tags years 2–5.

Rendering "missing" for five of seven filers would assert a deficiency that does not exist. Absent means **absent**: the component returns `null`.

If this feels like it contradicts the house style, that is because it nearly does. It is scoped to this one component and nowhere else.

### The basis error that will look correct

The ladder and `total_debt` are different measurements, and the numbers are close enough that a wrong rendering will look plausible. Verified 2026-08-05 against real filed figures:

| filer / year | ladder sum | filed total_debt | gap |
|---|---|---|---|
| QSR FY2023 | 13,043M | 12,921M | +122M (+0.9%) |
| CP FY2023 | 23,133M | 22,494M | +639M (+2.8%) |
| CP FY2021 *(truncated)* | 7,376M | 20,127M | −63% |

The ladder is **undiscounted contractual principal**; `total_debt` is **balance-sheet carrying amount**, net of unamortized discount and issue costs. So:

- Do not render "% of total debt" per bucket.
- Do not render a "total" row implying it reconciles.
- Do not stack the profile against the near-term share as though the first bucket were its breakdown — for CP those two differ in 11 of 15 shared years.

A stacked bar or a share-of-total treatment is the natural design instinct here and it is **wrong**. Show absolute amounts per bucket.

### Reference values for the two golden years

QSR FY2023 — y1 67M, y2 706M, y3 84M, y4 115M, y5 3,505M, thereafter 8,566M.
CP FY2023 (CAD) — y1 3,133M, y2 933M, y3 1,990M, y4 7M, y5 1,868M, thereafter 15,202M.

Re-confirm both live at build time. Story 5.6 exists as a cautionary tale: it was scoped on a spike whose central claim was false and two of whose coverage findings were wrong, and only the build-time re-check caught it.

### Currency

CP reports in CAD; every other us-gaap filer in USD. The near-term share sidesteps this by being a ratio. **This story displays absolute amounts, so it does not.** Do not label the axis or values "USD". `canonical_facts.unit` carries the real unit — use it, or omit the currency entirely.

### Project structure

- Mapping specs: `backend/canonicalization/mappings/specs/` — new version files, registry bump.
- Engine: extend `backend/debt/` (`engine.py` or a sibling in the same package).
- Spec: `backend/formulas/specs/` — `kind: thesistrace_presentation_rule`, refused by the model-spec loader and vice versa.
- API: `backend/api/schemas.py` + `repository.py`.
- UI: `frontend/app/components/`, wired in `frontend/app/company/[ticker]/page.tsx`.
- Tests: `backend/tests/`.

### Testing

- `pytest` with `TEST_DATABASE_URL` set and `DATABASE_URL` / `LLM_API_KEY` **unset** — the teardown drops all tables and will wipe the dev DB otherwise.
- Never let a test infer a precondition from ambient env; pin `Settings(_env_file=None)` where relevant.
- Baseline on `main` at story start: **207 passed, 1 skipped**.
- `ruff check`, `npx tsc --noEmit`, `npm run build` all clean before commit.
- `sprint-status.yaml` is now validated by `backend/tests/test_sprint_status.py` — updating story status there is enforced, not optional.

### Deployment note carried from 5.6

`MAPPING_VERSION` is already at `concepts_v6` and production has not been re-canonicalized. This story bumps it again. Flag both in the PR — one re-canonicalization pass covers both.

## Dev Agent Record

### Agent Model Used

claude-opus-5

### Debug Log References

- Live coverage verified from the Story 5.6 cached company-facts payloads (same session, fetched 2026-08-04 under the approval Lawrence gave then). No new EDGAR fetch was required.
- Task 1 output confirmed the story's predicted shape exactly: CP complete FY2022-2025 / truncated FY2010-2021, QSR complete FY2014-2024 / truncated FY2025, OTEX no usable profile, SHOP+CCJ+BCE+SU none.

### Completion Notes List

**Two real defects found, one of them pre-existing on `main`.**

1. **Undefined CSS tokens.** The component used `--color-surface-sunken`, `--radius-sm` and `--color-rule`, none of which exist in `globals.css`. `tsc` and `next build` both pass on these — an unresolvable `var()` is valid CSS. The bar track would have rendered invisible. Fixed to `--color-canvas`, `--radius-chip`, `--color-border`, and an audit of every `var()` in `app/**/*.tsx` now shows all resolve.
   **`--color-rule` was already live on `main`** via `NearTermDebtShare.tsx` (Story 5.6, PR #46) — its attribution divider was drawing in `currentColor` rather than the intended rule colour. Fixed here too.

2. **AC 5 violated in the rendered page, not in the data.** CP FY2023 shows "3.1B of 22.5B" in the near-term share card and `3.13B` as the first row of the schedule directly beneath it — 3,143M carrying amount vs 3,133M undiscounted principal, which at display precision read as one figure restated. Worse on QSR, where the two are *numerically identical* (67M) by coincidence. The attribution now defuses both misreadings explicitly, and a test asserts it covers each.

**Deliberate design choices, from the story's open questions:** bar row with values alongside (a cliff is what the reader is looking for); latest year leading with earlier years behind a disclosure, mirroring the near-term share card; golden pinned for QSR FY2023 and CP FY2023 only.

**Not exercised in the browser:** the truncation notice. The committed CP fixture carries only FY2022-2023, both of which are complete years, so no seeded filer-year is truncated. Covered by unit test (`test_missing_thereafter_is_reported_as_truncated`) and by the per-row `*` marker in the earlier-years table, but not seen rendered. Worth a look if the fixture ever gains a pre-FY2022 CP year.

**Guard refined, not deleted:** `test_maturity_ladder_tags_are_not_mapped` became `test_maturity_ladder_never_feeds_the_near_term_share`, narrowed to the invariant it was actually protecting. A second test pins `RemainderOfFiscalYear` as belonging to neither rule.

230 passed, 1 skipped. `ruff`, `tsc`, `next build` clean.

### File List

- `backend/canonicalization/mappings/specs/us-gaap_v6.yaml` (new)
- `backend/canonicalization/mappings/specs/registry.yaml` (modified — `concepts_v7`)
- `backend/formulas/specs/debt_maturity_profile_v1.yaml` (new)
- `backend/debt/profile.py` (new)
- `backend/api/schemas.py` (modified)
- `backend/api/repository.py` (modified)
- `backend/tests/test_maturity_profile.py` (new)
- `backend/tests/test_near_term_debt_share.py` (modified — guard refined)
- `backend/tests/test_concept_mappings.py` (modified — `NON_MODEL_CONCEPTS`)
- `backend/tests/test_golden_dataset.py` (modified — profile assertions)
- `backend/tests/golden/phase1_golden.yaml` (modified — all 7 companies)
- `backend/tests/fixtures/{qsr,cp,otex}_company_facts.json` (modified)
- `frontend/app/components/MaturityProfile.tsx` (new)
- `frontend/app/components/NearTermDebtShare.tsx` (modified — token fix)
- `frontend/app/company/[ticker]/page.tsx` (modified)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified)

### Change Log

- 2026-08-05 — Implemented Story 5.7. `MAPPING_VERSION` `concepts_v6` -> `concepts_v7`.

## References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.7] — acceptance criteria, "enrichment not a metric" framing
- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.6] — the corrected ladder-vs-carrying-amount finding this story must not undo
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml#story_5_1_debt_maturity_spike] — original ladder coverage + the 5.7 correction block
- [Source: architecture/ARCHITECTURE-SPINE.md#AD-16] — tri-state; and why this component is a scoped exception
- [Source: architecture/ARCHITECTURE-SPINE.md#AD-19] — provenance is a first-class invariant
- [Source: architecture/ARCHITECTURE-SPINE.md#AD-1] — read path is one pass over materialized rows
- [Source: architecture/ARCHITECTURE-SPINE.md#AD-2] — never edit a spec a stored mapping_version points at
- [Source: ux-designs/.../EXPERIENCE.md#State Patterns] — the `insufficient_data` convention this story deliberately departs from
- [Source: .claude/context/project-context.md] — anti-patterns: per-year tag coverage, no off-the-shelf charting, browser check mandatory
- [Source: backend/canonicalization/mappings/specs/us-gaap_v5.yaml#Story 5.6 header] — live evidence that ladder ≠ current-portion
- [Source: backend/formulas/specs/near_term_debt_share_v1.yaml] — the presentation-rule pattern to mirror
- [Source: backend/debt/engine.py] — filed-zero-is-a-value handling and `shares_for_facts` shape

## Open Questions for Lawrence

1. **Chart or table?** The profile is 6 buckets × 1 year. A simple labelled bar row reads well and is cheap; a table is more precise and trivially accessible. Recommendation: **bar row with values printed alongside**, since the point of the story is spotting a *cliff* visually. Either satisfies the ACs.
2. **Which fiscal year(s)?** The near-term share card shows the latest year with earlier years behind a disclosure. Recommendation: **mirror that** — latest year's profile, earlier years collapsed — rather than inventing a second pattern.
3. **Golden scope.** Recommendation: pin QSR FY2023 and CP FY2023 only (the two active golden years with a complete ladder). Pinning CP's truncated years would encode a truncation as an expectation.
