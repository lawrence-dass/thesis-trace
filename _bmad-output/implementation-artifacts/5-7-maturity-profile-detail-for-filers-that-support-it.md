# Story 5.7: Maturity profile detail for filers that support it

Status: ready-for-dev

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

- [ ] **Task 1 — Live-verify ladder coverage** (AC: 7)
  - [ ] Fetch company-facts for all 7 filers; the cached payloads from Story 5.6 are in the session scratchpad, otherwise re-fetch (**ask Lawrence once, naming every CIK** — standing preference).
  - [ ] Confirm per-year coverage of the six ladder buckets, bucketing by `period_end` against each issuer's own FYE, **not** the payload's `fy` field.
  - [ ] Confirm the expected shape: QSR full ladder FY2014–2024 (FY2025 missing thereafter), CP years 1–5 FY2010–2025 with thereafter only FY2022–2025, OTEX never tags years 2–5, SHOP/CCJ/BCE/SU none at all.

- [ ] **Task 2 — Map the six ladder buckets** (AC: 7, 9)
  - [ ] Add `us-gaap_v6.yaml` + `derivations_v4.yaml` if needed; bump registry to `concepts_v7`. **Never edit a spec a stored `mapping_version` points at** (AD-2).
  - [ ] New concepts: `debt_maturity_year_1` … `debt_maturity_year_5`, `debt_maturity_thereafter`.
  - [ ] `ifrs-full`: map nothing. The IFRS maturity analysis is dimensional and structurally unreachable via company-facts (Story 5.1 finding, still true).
  - [ ] Refine `test_maturity_ladder_tags_are_not_mapped` per AC 9.
  - [ ] Update `NON_MODEL_CONCEPTS` in `test_concept_mappings.py` — these feed a presentation rule, not a model, so the both-regimes rule does not apply.

- [ ] **Task 3 — Profile engine** (AC: 3, 4, 5)
  - [ ] Extend `backend/debt/` (do **not** create a parallel module — reuse the existing package).
  - [ ] Return an ordered bucket list plus an explicit `truncated: bool` when `thereafter` is absent.
  - [ ] A filer-year with no year-2..5 buckets yields **no profile at all** — not an empty list rendered as a profile.
  - [ ] `Decimal` throughout, never `float` (AD-15).
  - [ ] Spec: extend `near_term_debt_share_v1.yaml` **or** add a sibling `kind: thesistrace_presentation_rule` spec. Either way the basis warning must be a machine-readable field, not a YAML comment (this trap has now recurred three times — D8 `derivations_v2`, 5.5 `trajectory_v1`, and it is called out again here).

- [ ] **Task 4 — API** (AC: 1, 6)
  - [ ] Add to `CompanyOverviewOut`. One query for all six concepts across all years, then a pure computation — mirror the `near_term_debt_share` pass; **must not** become an N+1 (AD-1).
  - [ ] Provenance per bucket (AD-19).

- [ ] **Task 5 — UI** (AC: 1, 2, 3, 5)
  - [ ] New component under `frontend/app/components/`, rendered beneath `NearTermDebtShareCard`, inside `quality_health` only.
  - [ ] Return `null` when there is no profile — no wrapper, no heading, no badge.
  - [ ] Truncation notice when `truncated`.
  - [ ] Custom visualization only — **no TradingView or off-the-shelf charting** (standing project rule).
  - [ ] Theme-aware, and horizontal overflow must scroll inside its own container.

- [ ] **Task 6 — Golden + verification** (AC: 8)
  - [ ] Extend fixtures with the six tags, reusing **only accessions already present** so existing hand-verified values cannot shift.
  - [ ] Extend `phase1_golden.yaml` for QSR FY2023 and CP FY2023 (both active golden years with a complete ladder).
  - [ ] Hand-compute independently — **import nothing** from `backend/debt`.
  - [ ] Confirm the guard bites by corrupting an expected value.
  - [ ] **Render it in a browser.** Mandatory, not diligence — it found 4 real bugs in 5.4 and 1 in 5.6 that tests could not.

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

### Completion Notes List

### File List

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
