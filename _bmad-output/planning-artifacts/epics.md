---
stepsCompleted: [step-01-validate-prerequisites, step-02-design-epics, step-03-create-stories, step-04-final-validation]
inputDocuments:
  - _bmad-output/specs/spec-thesistrace/SPEC.md
  - _bmad-output/planning-artifacts/prds/prd-ThesisTrace-2026-07-17/prd.md
  - _bmad-output/planning-artifacts/architecture/architecture-ThesisTrace-2026-07-19/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/foundational-decisions.md
---

# ThesisTrace - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for ThesisTrace, decomposing the requirements from the SPEC (capabilities CAP-1…CAP-14), the PRD (FR-1…FR-21), and the Architecture spine (AD-1…AD-21) into implementable stories. **Scope of this run: Phase 1 (CAP-1…CAP-9 / FR-1…FR-14).** FR-15…FR-21 (Filing Q&A, Value/Growth lenses, Thesis Journal, Notifications) are Phase 2/3 directional and are intentionally NOT decomposed into stories here.

No UX design contract exists yet (bmad-ux was not run); UX-derived stories are therefore out of scope for this run, and UI stories reference the PRD user journeys (UJ-1…UJ-3) and the "custom visualizations, no off-the-shelf widgets" constraint (D7) directly.

## Requirements Inventory

### Functional Requirements

**Phase 1 — in scope for this run:**

- **FR-1** (CAP-1): Starter list display — any visitor views the Company Universe (CP, QSR, OTEX, SHOP) as explorable cards on the landing page, no auth; each card shows name, ticker, last-updated and links to the overview.
- **FR-2** (CAP-1): Ticker search — an in-universe ticker navigates to its overview; an out-of-universe ticker returns an explicit "not yet covered" message, never a silent failure or fabricated result.
- **FR-3** (CAP-2): Piotroski F-Score computation — all 9 signals individually computed and stored; formula versioned; missing input marked `insufficient_data`, never guessed.
- **FR-4** (CAP-2): Altman Z-Score computation — all 5 ratios individually computed/stored; market value of equity = FYE Tiingo close × EDGAR shares outstanding (never book-value substitute); financial-sector firms excluded, capital-intensive firms caveated; formula versioned.
- **FR-5** (CAP-3): Quality/Health sub-signal display — each Piotroski signal (pass/fail) and Altman component shown with specific compared values, each linking to its provenance record.
- **FR-6** (CAP-4): Beneish M-Score computation — all 8 indices individually computed/stored; formula versioned; financial-sector firms excluded.
- **FR-7** (CAP-4): Sloan accruals ratio computation — balance-sheet approach across two consecutive balance sheets; flagged against an explicitly stated published threshold.
- **FR-8** (CAP-5): Integrity sub-signal display & provenance — each Integrity signal's inputs and source filing line item viewable; accounting-identity validation failures surface as explicit data-quality warnings, never hidden.
- **FR-9** (CAP-6): Company overview page (Verdict) — transparent per-model threshold-classification juxtaposition (never blended, never LLM-invented, band labels computed backend); states which lenses are live vs pending; individual scores stay visible/clickable.
- **FR-10** (CAP-6): Expandable sub-factor breakdown — in-page accordion expansion, each sub-signal linking onward to its methodology page.
- **FR-11** (CAP-7): Methodology page per score — states the formula, the exact XBRL concepts mapped to each input, the formula version, and links to the model's original academic source.
- **FR-12** (CAP-8): Cited narrative explanation — deterministic template from computed scores/facts; LLM (Claude Haiku 4.5, env-keyed, no LangGraph) polishes only, never originates a claim/number/citation; inline citations; ungroundable statements omitted.
- **FR-13** (CAP-9): Add to comparison — browser-session-only comparison set, min 2 / max 4 companies.
- **FR-14** (CAP-9): Side-by-side comparison view — parallel columns of Verdicts and currently-live lens scores; differences beyond a stated threshold visually highlighted.

**Phase 2/3 — directional, NOT decomposed in this run:**

- **FR-15** (CAP-10, Phase 2): Cited filing Q&A — LangGraph self-verifying citation loop.
- **FR-16** (CAP-11, Phase 2): Valuation metrics — assumptions + sensitivity ranges, never a bare point estimate.
- **FR-17** (CAP-12, Phase 2): Growth trajectory metrics — historical trends honest about coverage window.
- **FR-18** (CAP-13, Phase 2/3): Thesis save and re-verification — browser-local, per-claim Thesis Diff.
- **FR-19** (CAP-14, Phase 3): Thesis re-verification notification — email once per new filing per thesis.
- **FR-20** (CAP-14, Phase 3): Deep research request submission — email-only, stated SLA.
- **FR-21** (CAP-14, Phase 3): Deep research request fulfillment notification — cited result via real transactional email provider.

### NonFunctional Requirements

The PRD deliberately sets **no formal performance/uptime/security/accessibility NFR targets for v1** (§5 Non-Goals) — correctness is the quality bar. The following are the binding quality attributes that DO constrain Phase-1 implementation, derived from the SPEC constraints, foundational decisions, and architecture ADs:

- **NFR-1 (Correctness — the bar):** 100% of Piotroski/Altman/Beneish/Sloan scores for CP/QSR/OTEX/SHOP match a hand-verified or published golden dataset, enforced by a regression harness (SM-1). Harness is Phase-1 scope; only its CI automation is Phase-4.
- **NFR-2 (Numeric integrity):** every financial figure stored/computed is `NUMERIC`/`DECIMAL`, never float; rounding uses one enumerated policy (default `ROUND_HALF_EVEN`) applied by a single shared decimal engine (AD-15, AD-5).
- **NFR-3 (EDGAR access discipline):** identifying User-Agent, ≤10 req/s, cached, retried with backoff, idempotent by `(accession_number, content_hash)`, replayable (AD-9).
- **NFR-4 (Provenance):** every displayed canonical value and score input resolves end-to-end to `(accession_number, xbrl_concept/line item, filing period, source)`; a value with no resolvable provenance is not shown as fact (AD-19).
- **NFR-5 (Deterministic/LLM boundary — inviolable):** the LLM never originates or alters a number, score, threshold, or verdict input (D5, AD-7).
- **NFR-6 (Cost):** total running cost stays ≤ ~$25/month; Phase-1 fixed cost ~$8–10/mo (Render + free tiers).
- **NFR-7 (No end-user auth):** public, read-only; admin/recompute operator-only behind a shared-secret header (D4, AD-10).
- **NFR-8 (CQRS discipline):** all computation runs in the scheduled batch pipeline; the read path (FastAPI/Next.js) only queries materialized Postgres and never computes a score or calls EDGAR/Tiingo live (AD-1, AD-10).
- **NFR-9 (Deferred by design):** no formal performance, uptime, security, or WCAG targets for v1 — recorded so downstream does not invent them.

### Additional Requirements

Derived from the Architecture spine (AD-1…AD-21) and Deployment section:

- **Greenfield, no third-party starter template.** The build follows the spine's own source tree: `frontend/` (Next.js, presentation only), `backend/` (`ingestion/`, `raw_store/`, `canonicalization/`, `validation/`, `formulas/`, `scoring/`, `explanation/`, `api/`), `db/migrations/`. → **Epic 1, Story 1** is project scaffold + infra wiring, not a template adoption.
- **Hosting/infra (AD-13):** FastAPI read API as a Render Web Service; batch pipeline as a Render Cron Job (one platform/bill); Next.js on Vercel; Supabase Postgres 17. The daily scheduled ingestion job doubles as the Supabase keep-alive ping. Single production env + local dev; no staging tier.
- **Data model (structural seed):** `issuers` (CIK key), `filings` (accession_number key), `raw_facts` (append-only), `concept_mappings` (versioned), `canonical_facts`, `market_prices`, `score_runs` (append-only, supersede-not-mutate), `score_inputs`, `score_results`, `data_quality_issues`. Internal PKs UUID; `DATE` for fiscal/filing dates, `TIMESTAMPTZ` for computed/fetched.
- **Versioned formula specs as code (AD-5):** `formulas/<model>_v1.yaml` carrying equation, inputs, thresholds, rounding mode, missing-data/divide-by-zero policy, `signal_key` vocabulary, and cited band copy. `score_run.formula_version` references the spec by string.
- **Dual-source ingestion (AD-4):** SEC Company Facts API primary + Inline XBRL fallback for omitted facts; on conflict Company Facts wins and the divergence writes a `data_quality_issues` row.
- **Canonical-fact selection rules (AD-3):** as-originally-filed > restated comparative; least-dimensioned/most-specific member; higher decimals; unresolved ambiguity writes `data_quality_issues:needs_review`.
- **Contracts to enforce across seams:** tri-state signal status (AD-16), single `data_quality_issues` shape/owner (AD-17), canonical `score_results` shape + `signal_key` (AD-18), sector-scope applicability state (AD-20), FastAPI error envelope `{error:{code,message,details}}`, `not_available` success envelope for a lens not yet covered.
- **Config via env vars only for secrets:** EDGAR contact, Tiingo key, LLM (Claude) key, DB connection — never hardcoded.
- **Amendment policy (AD-6):** a 10-K/A triggers a new append-only `score_run`; prior run marked superseded; current = latest non-superseded.

### UX Design Requirements

None — no UX design contract (bmad-ux run) exists. UI stories will reference PRD user journeys UJ-1…UJ-3 and the custom-visualization constraint (D7) directly. Producing a UX design contract via `bmad-ux` before UI-heavy stories is an optional recommended follow-up.

### FR Coverage Map

Each Phase-1 FR is owned by exactly one epic (where it is *completed*). Epic 1's thin display is a deliberate pre-FR walking-skeleton, so it owns only the two score-computation FRs.

- **FR-1** → Epic 4 — Starter list display
- **FR-2** → Epic 4 — Ticker search ("not yet covered" handling)
- **FR-3** → Epic 1 — Piotroski F-Score computation
- **FR-4** → Epic 2 — Altman Z-Score computation (Tiingo market value of equity)
- **FR-5** → Epic 2 — Quality/Health sub-signal display with provenance (all models)
- **FR-6** → Epic 2 — Beneish M-Score computation
- **FR-7** → Epic 1 — Sloan accruals ratio computation
- **FR-8** → Epic 2 — Integrity sub-signal display, provenance & data-quality flags
- **FR-9** → Epic 3 — Company overview page (Verdict juxtaposition)
- **FR-10** → Epic 3 — Expandable sub-factor breakdown
- **FR-11** → Epic 3 — Methodology page per score
- **FR-12** → Epic 3 — Cited narrative explanation (deterministic-first)
- **FR-13** → Epic 4 — Add to comparison
- **FR-14** → Epic 4 — Side-by-side comparison view
- *FR-15…FR-21 → Phase 2/3, not decomposed in this run.*

## Epic List

### Epic 1: Foundation & First Evidence (Walking Skeleton)
A visitor can open a real company (Shopify first, then the full universe) and see a genuine forensic score — Piotroski F-Score and Sloan accruals ratio — traced to the actual EDGAR filing line item, proving the entire deterministic batch pipeline end-to-end on live data. Establishes project scaffold + Render/Vercel/Supabase infra, the data model, EDGAR ingestion (Company Facts + Inline XBRL fallback), canonicalization + validation, versioned formula specs, append-only scoring, the read-only query API, a thin overview page, and the golden-dataset regression harness. Uses only EDGAR (no Tiingo dependency yet).
**FRs covered:** FR-3, FR-7

### Epic 2: Complete the Four Lenses
A visitor sees all four forensic models for every company, each with full sub-signal detail and field-level provenance. Adds Altman Z-Score (with Tiingo market-price ingestion, `market_prices`, and sector applicability) and Beneish M-Score (with sector exclusion), and builds out the complete Quality/Health and Integrity sub-signal displays including accounting-identity data-quality warnings. Extends the golden-dataset harness to all four models across the full universe.
**FRs covered:** FR-4, FR-6, FR-5, FR-8

### Epic 3: Verdict, Methodology & Explanation
A visitor gets a glanceable, honest Verdict per company, can drill into any factor in-page, read the exact methodology behind each score, and request a cited plain-language explanation. Builds the overview Verdict (transparent per-model threshold juxtaposition with phase-honesty), the in-page expandable breakdown, the per-score methodology pages, and the deterministic-first, citation-grounded AI explanation (Claude Haiku, never in the numeric loop).
**FRs covered:** FR-9, FR-10, FR-11, FR-12

### Epic 4: Discovery & Comparison
A visitor discovers the Company Universe from the landing page, searches for tickers (with an honest "not yet covered" for anything outside the universe), and compares 2–4 companies side by side across whichever lenses are live. Completes the discovery shell and the session-scoped comparison experience around the now-complete company pages.
**FRs covered:** FR-1, FR-2, FR-13, FR-14

---

## Phase 2 Epic List *(added 2026-08-04)*

Sequenced by **`foundational-decisions.md` D9** — around one real investment decision, not around the
lens list. Epics 1–4 are complete; Phase 2 begins at Epic 5.

> **Decomposition is deliberately uneven, and that is the decision, not an omission.** Epics 5, 6
> and 10 are fully decomposed. Epic 7 carries intent and scope but no stories. Epics 8–9 are
> headlines only.
>
> **Corrected 2026-08-06.** This note previously read that decomposing an epic "would commit to an
> ordering the first real decision packet is explicitly allowed to overturn," and used that to defer
> Epics 6–9 as a block. That inference does not hold. **D9's binding criterion governs BUILD order —
> which feature is built next — not planning order.** Acceptance criteria commit nothing; a story can
> sit in the backlog unbuilt indefinitely. Conflating "we planned it" with "we committed to it"
> treated four epics with four different blockers as one case.
>
> The honest test is per-epic: **can its acceptance criteria be written truthfully today?** Epic 6's
> could, once Story 6.1's spike answered the data question and its five remaining product questions
> were recorded as assumptions rather than findings. Epic 7's cannot until the thesis-storage
> contradiction is resolved — "on return the system diffs" requires persistence, and Phase 1 has no
> auth. Epic 8's need a metric selection and an unequal-history display rule, both makeable but not
> yet made. Epic 9's would reference a citation-evaluation framework that does not exist.
>
> D9 is unchanged and still binding: **what gets built next is still chosen from the largest observed
> research failure.** A planned backlog is what that choice selects *from*.

### Epic 5: Filing Change Detection & Quality-Lens Depth
Lawrence opens a company he last looked at weeks ago and sees, immediately and citably, what moved — new filing ingested, canonical facts changed, score bands crossed, data-quality issues opened or resolved — plus the two Quality/Health sub-metrics adopted under PRD OQ9. First increment of the decision workflow: you cannot evaluate a thesis without first knowing what changed. *(OQ9's "debt maturity concentration" was redefined to near-term debt share on 2026-08-04 after the Story 5.1 spike found only 2 of 7 filers carry a usable ladder.)*
**FRs covered:** FR-22 (new), FR-5 (extended)

### Epic 6: Narrow Valuation — Reverse DCF
Lawrence sees what growth and margin assumptions the *current market price* implies for a company, with every assumption explicit and a sensitivity range — never a bare fair-value point estimate. Deliberately a narrow slice of FR-16, not the full Value lens: reverse DCF only, because it answers "is the price reasonable?" while making the model's assumptions the visible output rather than hiding them behind a single number.
**FRs covered:** FR-16 (partial — reverse DCF only)

### Epic 7: Thesis Journal & Thesis Diff
Lawrence writes a thesis for a company, it is auto-attached to the live facts and scores cited at that moment, and on return the system diffs those specific cited claims against current values. The feature most directly tied to the product's name, and the one that closes the decision loop by making a thesis falsifiable.
**FRs covered:** FR-18

### Epic 8: Growth Trends *(headline only — do not decompose yet)*
Growth trajectory metrics across each company's genuinely available history, at the depth the decision workflow proves it needs. Trend depth must honestly reflect per-filer coverage — IFRS 40-F filers start ~FY2017 (~9 years) versus OTEX's 24 under `us-gaap`, so no fixed decade-long promise.
**FRs covered:** FR-17

### Epic 9: Filing Q&A *(headline only — do not decompose yet)*
Citation-grounded Q&A over a company's filings via LangGraph's self-verifying citation loop. Last by design (D9): it is the heaviest lift in the roadmap and depends on a citation-evaluation framework that does not yet exist.
**FRs covered:** FR-15

### Epic 10: Report-Style Company Page
Lawrence opens a company and reads a sectioned stock report — an overview with an original four-model glyph and rule-derived rewards/risks, then Valuation, Past Performance, Financial Health, and Integrity & Evidence — presented with Simply Wall St-grade visual clarity but built exclusively from ThesisTrace's own already-computed deterministic figures (**D12**, added 2026-08-27). Presentation-only by definition: no new computation, ingestion or figures, which is why it is buildable now while Epics 7-9 stay blocked — D9's gate governs new capabilities, and this adds none.
**FRs covered:** none new — re-presents the shipped surfaces of FR-9, FR-10, FR-5, FR-8, FR-22 and FR-16

### Epic 11: UI Redesign — Instrument Panel
Lawrence's stated concern (2026-08-28): Epic 10's report shell is functionally complete but still reads as a data dashboard, not something that teaches the four models while it reports them. A five-direction design-exploration pass (published as comparable Artifacts, real QSR data, both themes) selected **Instrument Panel** — terminal-precision JetBrains Mono, a muted amber accent, and click-to-expand inline definitions on every jargon term as the core teaching mechanism. This epic re-skins Epic 10's report end to end and adds two new presentation-layer capabilities the exploration surfaced: inline term definitions (reusable everywhere a signal key or model term appears) and model-level "why this works" explainers with worked examples on the existing `/methodology/[model]` pages, closing the gap between mechanical signal-level definitions and actually teaching the four models. Presentation-only in the same sense as Epic 10 — no score, figure, or computation changes; D9's capability gate does not govern it.
**FRs covered:** none new — re-skins the shipped surfaces of Epic 10 and extends Epic 3's methodology pages; the inline-definition component and the methodology explainers are new UI/content, not a new capability under D9

### Epic 12: US Universe Expansion — Campbell's & Zoetis
Lawrence has a real, staked decision to buy CPB and ZTS (decision packets `2026-09-01-CPB.md`, `2026-09-01-ZTS.md`, satisfying D11 — each filer is added because it is being researched, not researched because it was added). Both are plain US-GAAP 10-K filers. Live coverage verification on 2026-09-01 found CPB's current canonical revenue range at FY2017-2025 and ZTS's at FY2016-2025; ZTS's legacy `SalesRevenueNet` explains the FY2014 gap but is not yet mapped, while CPB's `SalesRevenueGoodsNet` remains rejected pending continuing-operations reconciliation. ZTS's restricted-inclusive cash tag also requires issuer-specific handling. This is the same shape of work as Epic 1's original onboarding and D8's IFRS track — ingest, canonicalize, extend the golden dataset, verify live — not a new taxonomy or a new capability. Universe growth under D11, not an Epic 7-9 capability, so D9's gate does not apply.
**FRs covered:** none new — extends the existing ingestion/canonicalization/scoring pipeline (FR-1 through FR-14, FR-22, FR-16) to two additional filers already-supported under `us-gaap`

---

## Epic 1: Foundation & First Evidence (Walking Skeleton)

Prove the entire deterministic batch pipeline end-to-end on live EDGAR data: from a fresh repo to a visitor seeing Shopify's real Piotroski F-Score and Sloan accruals ratio, each traceable to the filing line item. Uses EDGAR only (no Tiingo). Establishes every seam the later epics build on. *(FR-3, FR-7; NFR-1…NFR-8; AD-1…AD-10, AD-13, AD-15, AD-16, AD-17, AD-18.)*

### Story 1.1: Project scaffold and deployable skeleton

As Lawrence (operator/developer),
I want the monorepo, FastAPI service, Next.js app, and Supabase connection scaffolded and deployable,
So that every later story has a working, hosted foundation to build on.

**Acceptance Criteria:**

**Given** an empty repository
**When** the scaffold story is complete
**Then** the source tree matches the architecture spine (`frontend/` Next.js, `backend/` with `ingestion/ raw_store/ canonicalization/ validation/ formulas/ scoring/ explanation/ api/`, `db/migrations/`)
**And** the FastAPI app exposes a `/health` endpoint that returns 200, deployable as a Render Web Service (AD-13)
**And** the Next.js app builds and deploys to Vercel and can call the FastAPI health endpoint
**And** all secrets (DB URL, EDGAR contact, Tiingo key, LLM key) load from environment variables only, never hardcoded, with a committed `.env.example`
**And** the app connects to a Supabase Postgres 17 instance using SQLAlchemy async.

### Story 1.2: Core data model and migrations for the scoring slice

As Lawrence (developer),
I want the tables needed for EDGAR ingestion through scoring created via migrations,
So that raw facts, canonical facts, and score runs have a durable, correctly-typed home.

**Acceptance Criteria:**

**Given** the scaffolded backend and a Supabase database
**When** migrations run
**Then** these tables exist: `issuers` (CIK string key), `filings` (accession_number key), `raw_facts`, `concept_mappings`, `canonical_facts`, `score_runs`, `score_inputs`, `score_results`, `data_quality_issues` (the `market_prices` table is intentionally deferred to Epic 2)
**And** every financial figure column is `NUMERIC`/`DECIMAL`, never float/double (AD-15)
**And** internal PKs are UUID except the two natural-key tables; fiscal/filing dates are `DATE`, computed/fetched timestamps are `TIMESTAMPTZ` (AD-15 conventions)
**And** `raw_facts` is append-only keyed by `(accession_number, content_hash)` (AD-2); `score_results` follows the canonical shape `(score_run_id, model, signal_key, value, status, band_label, threshold_ref)` (AD-18); `data_quality_issues` has one row shape with a closed status enum `needs_review|resolved|dismissed` (AD-17).

### Story 1.3: EDGAR ingestion for Shopify

As the system,
I want to ingest Shopify's EDGAR filing facts with SEC-compliant access discipline,
So that raw source data is captured immutably and reproducibly.

**Acceptance Criteria:**

**Given** Shopify's CIK
**When** ingestion runs
**Then** the SEC Company Facts API is the primary source and raw Inline XBRL is the fallback for facts Company Facts omits (AD-4)
**And** requests use an identifying User-Agent, stay at or under 10 req/s, and cache + retry with backoff (AD-9)
**And** ingestion is idempotent by `(accession_number, content_hash)` and re-running it creates no duplicate `raw_facts` rows (AD-2, AD-9)
**And** on a value conflict between the two sources for the same fact, Company Facts wins and the divergence writes a `data_quality_issues` row (AD-4).

### Story 1.4: Canonicalization and validation

As the system,
I want raw facts canonicalized by versioned mappings with deterministic selection and validation,
So that scoring reads unambiguous, audited canonical facts.

**Acceptance Criteria:**

**Given** ingested `raw_facts` for Shopify
**When** canonicalization runs
**Then** canonical facts are produced via versioned `concept_mappings`, never mutated in place (AD-2)
**And** fact selection follows the deterministic order: as-originally-filed over restated comparative, least-dimensioned/most-specific member, higher decimals precision (AD-3)
**And** any unresolved ambiguity writes a `data_quality_issues` row with status `needs_review` rather than defaulting a value (AD-3)
**And** a failed accounting-identity check (e.g. balance sheet doesn't balance) writes a data-quality warning, never silently hidden (AD-17).

### Story 1.5: Versioned formula-spec engine with shared decimal engine

As Lawrence (developer),
I want formula specs loaded from versioned YAML and evaluated through one shared decimal/rounding engine,
So that every score is reproducible and two evaluators can't diverge at a threshold boundary.

**Acceptance Criteria:**

**Given** a formula spec file (e.g. `formulas/piotroski_v1.yaml`)
**When** the engine loads it
**Then** the spec carries the equation, inputs, thresholds, rounding mode, missing-data policy, divide-by-zero policy, `signal_key` vocabulary, and cited band copy (AD-5)
**And** all arithmetic runs through one shared decimal engine using the spec's enumerated rounding mode (default `ROUND_HALF_EVEN`), never a per-module choice (AD-15)
**And** a score run records the exact `formula_version` string it used (AD-5).

### Story 1.6: Compute and store the Piotroski F-Score (FR-3)

As the system,
I want to compute Shopify's Piotroski F-Score with each signal stored individually,
So that the score is transparent and reproducible.

**Acceptance Criteria:**

**Given** canonical facts for two consecutive fiscal years
**When** the Piotroski score runs
**Then** all 9 binary signals are individually computed and stored as `score_results` rows, not just the aggregate (FR-3)
**And** each signal carries a tri-state status `pass|fail|insufficient_data`; a missing input is `insufficient_data`, never guessed or defaulted to a failing 0 (FR-3, AD-16)
**And** the run is an append-only `score_run`; an amendment later creates a new run and supersedes the prior one rather than mutating it (AD-6)
**And** the result is retrievable by `signal_key` per the canonical `score_results` shape (AD-18).

### Story 1.7: Compute and store the Sloan accruals ratio (FR-7)

As the system,
I want to compute Shopify's Sloan accruals ratio with its threshold flag,
So that an earnings-quality signal is available with a stated, cited cutoff.

**Acceptance Criteria:**

**Given** canonical facts for two consecutive balance sheets
**When** the Sloan score runs
**Then** the ratio is computed via the balance-sheet approach and stored with tri-state status (FR-7, AD-16)
**And** it is flagged as high-accrual only when it crosses the threshold value pinned and cited in the versioned formula spec, with the threshold stated explicitly (FR-7, AD-5)
**And** the run is append-only and result rows follow the canonical `score_results` shape (AD-6, AD-18).

### Story 1.8: Read-only query API and thin company overview

As a visitor,
I want to open Shopify's page and see its Piotroski and Sloan scores traced to the filing,
So that the core promise is proven on a real company.

**Acceptance Criteria:**

**Given** stored scores for Shopify
**When** a visitor opens Shopify's overview page
**Then** the FastAPI endpoint returns the scores and their provenance from materialized Postgres only — it never computes a score or calls EDGAR live (AD-1, AD-10)
**And** the Next.js page renders Shopify's Piotroski F-Score and Sloan ratio, each signal linking to its provenance record `(accession_number, xbrl_concept/line item, filing period, source)` (AD-19, AD-8)
**And** all API errors use the envelope `{error:{code,message,details}}` and a not-yet-scored lens returns a success-envelope `not_available` state, never an error or a fabricated zero (AD conventions)
**And** the frontend contains no scoring logic and renders exactly what the API returns (AD-8).

### Story 1.9: Golden-dataset regression harness

As Lawrence (operator),
I want a regression harness asserting computed scores match a hand-verified golden dataset,
So that correctness (SM-1) is enforceable from the first story.

**Acceptance Criteria:**

**Given** hand-verified or published Piotroski and Sloan values for Shopify
**When** the regression suite runs
**Then** it asserts 100% match between computed and golden values and fails the build on any mismatch (NFR-1, SM-1)
**And** the harness is structured to accept the remaining companies and the Altman/Beneish models added in Epic 2
**And** the golden-value source for each figure is recorded alongside the expected value.

### Story 1.10: Scheduled pipeline across the full universe

As Lawrence (operator),
I want the batch pipeline scheduled and run for all four companies through Piotroski and Sloan,
So that the walking skeleton covers the committed universe and stays warm.

**Acceptance Criteria:**

**Given** the working Shopify slice
**When** the pipeline is scheduled
**Then** it runs as a Render Cron Job executing ingest → canonicalize → validate → score for CP, QSR, OTEX, and SHOP (AD-13, AD-1)
**And** all four companies have stored, provenance-linked Piotroski and Sloan scores viewable via their overview pages
**And** the scheduled run doubles as the Supabase keep-alive so the free-tier DB does not auto-pause
**And** the golden-dataset harness passes for all four companies on both models.

---

## Epic 2: Complete the Four Lenses

Bring every company to all four forensic models with full sub-signal detail and field-level provenance: add Altman (with the Tiingo market-price dependency) and Beneish, and build the complete Quality/Health and Integrity displays. *(FR-4, FR-5, FR-6, FR-8; AD-3, AD-4, AD-5, AD-11, AD-14, AD-16, AD-17, AD-18, AD-19, AD-20.)*

### Story 2.1: Tiingo market-price ingestion and market_prices table

As the system,
I want to ingest and persist period-end closing prices from Tiingo,
So that Altman's market value of equity can be computed without a live call at read time.

**Acceptance Criteria:**

**Given** a company and its fiscal-year-end date
**When** market-price ingestion runs
**Then** a `market_prices` table exists (`issuer_id, price_date, close_price, source, fetched_at`) with `close_price` as `NUMERIC` (AD-14, AD-15)
**And** the stored FYE price is the close on the last trading day on or before fiscal-year-end (AD-14)
**And** the Tiingo key loads from an env var and the fetch is persisted (never called live during a read request) (AD-14, AD-1)
**And** Tiingo is used solely for closing price — no other data provider is introduced (D7 exception).

### Story 2.2: Compute and store the Altman Z-Score (FR-4)

As the system,
I want to compute each company's Altman Z-Score with a real market value of equity and correct sector handling,
So that financial-distress signal is accurate and never misleading.

**Acceptance Criteria:**

**Given** canonical facts and a stored FYE market price
**When** the Altman score runs
**Then** all 5 weighted ratios are individually computed and stored (FR-4)
**And** market value of equity = FYE close (`market_prices`) × EDGAR `dei:EntityCommonStockSharesOutstanding`, never a book-value substitute (FR-4, AD-11)
**And** financial-sector firms carry applicability `excluded_out_of_scope` and capital-intensive firms carry `computed_with_caveat`; the API/frontend never show a bare number for those cases (AD-20, D6)
**And** the score is versioned and append-only with tri-state signals (AD-5, AD-6, AD-16).

### Story 2.3: Compute and store the Beneish M-Score (FR-6)

As the system,
I want to compute each in-scope company's Beneish M-Score with all eight indices,
So that earnings-manipulation risk is transparent.

**Acceptance Criteria:**

**Given** canonical facts for two consecutive fiscal years
**When** the Beneish score runs
**Then** all 8 indices (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA) are individually computed and stored (FR-6)
**And** financial-sector firms carry applicability `excluded_out_of_scope` (AD-20, D6)
**And** the score is versioned, append-only, with tri-state signals and the canonical `score_results` shape (AD-5, AD-6, AD-16, AD-18).

### Story 2.4: Quality/Health sub-signal display with provenance (FR-5)

As a visitor,
I want to see each Piotroski signal and Altman component individually with the values compared,
So that I can trust the Quality/Health lens down to the line item.

**Acceptance Criteria:**

**Given** computed Piotroski and Altman scores for a company
**When** a visitor views its Quality/Health detail
**Then** each of the 9 Piotroski signals shows pass/fail with the specific compared values (e.g. "ROA 2024 4.2% vs 2023 3.1% → Pass") (FR-5)
**And** each of the 5 Altman components shows its contribution weight (FR-5)
**And** every displayed value links to its provenance record (source filing and line item) (FR-5, AD-19)
**And** an `insufficient_data` signal is shown as such, never as a pass or fail (AD-16).

### Story 2.5: Integrity sub-signal display, provenance and data-quality flags (FR-8)

As a visitor,
I want to see each Integrity signal's inputs with provenance and any data-quality warnings,
So that I can judge earnings integrity with full evidence.

**Acceptance Criteria:**

**Given** computed Beneish and Sloan scores for a company
**When** a visitor views its Integrity detail
**Then** each Beneish index and the Sloan inputs display with their source filing line items (FR-8, AD-19)
**And** an accounting-identity validation failure appears as an explicit data-quality warning drawn from `data_quality_issues`, never silently hidden (FR-8, AD-17)
**And** the provenance-linking pattern matches the Quality/Health display (FR-8).

### Story 2.6: Extend the golden-dataset harness to all four models

As Lawrence (operator),
I want the regression harness to cover Altman and Beneish across the full universe,
So that SM-1 holds for all four models.

**Acceptance Criteria:**

**Given** hand-verified/published Altman and Beneish values for CP, QSR, OTEX, SHOP
**When** the regression suite runs
**Then** it asserts 100% match for all four models across the universe and fails the build on any mismatch (NFR-1, SM-1)
**And** sector-excluded cases assert `excluded_out_of_scope` rather than a numeric expectation.

---

## Epic 3: Verdict, Methodology & Explanation

Build the trust surface: an honest glanceable Verdict, in-page drill-down, exact methodology, and a cited plain-language explanation. *(FR-9, FR-10, FR-11, FR-12; AD-5, AD-7, AD-8, AD-12, AD-19, AD-20, AD-21.)*

### Story 3.1: Backend Verdict assembly and band classification

As the system,
I want each model's threshold band classified in the backend and exposed via the read API,
So that the frontend never recomputes cutoffs.

**Acceptance Criteria:**

**Given** stored scores for a company
**When** the Verdict is assembled
**Then** each live model's band label is computed in scoring and stored in `score_results.band_label` using the model's own published, cited bands — Piotroski Strong 8-9 / Weak 0-1 / 2-7 Middle-mixed; Altman Safe/Grey/Distress; Beneish > −1.78; Sloan per its spec threshold (FR-9, AD-8, AD-12)
**And** the read API returns per-model classifications plus which lenses are live vs pending and each model's applicability state (FR-9, AD-20)
**And** no blended or weighted single score is produced (FR-9, AD-12).

### Story 3.2: Company overview page with Verdict juxtaposition (FR-9)

As a visitor,
I want a company overview showing each live model's classification side by side with honest phase labeling,
So that I get a glanceable verdict without a black-box number.

**Acceptance Criteria:**

**Given** an assembled Verdict
**When** a visitor opens a company's overview
**Then** the page shows each live model's own cited threshold classification in parallel, never a single combined number (FR-9, AD-12)
**And** it states explicitly which lenses are live vs pending for that company (FR-9)
**And** individual lens scores remain visible and clickable — the visitor is never forced to accept only the summary (FR-9)
**And** the frontend renders the stored band labels and contains no scoring logic (AD-8).

### Story 3.3: Expandable in-page sub-factor breakdown (FR-10)

As a visitor,
I want to expand any lens score inline to see its sub-signals,
So that I can drill in without losing my place.

**Acceptance Criteria:**

**Given** a company overview page
**When** a visitor expands a lens score
**Then** the sub-signals appear in-page via an accordion/expandable section, not a modal or a new page (FR-10)
**And** each sub-signal links onward to its full methodology page (FR-10, FR-11).

### Story 3.4: Methodology page per score (FR-11)

As a visitor (or technical evaluator),
I want a dedicated methodology page for each score,
So that nothing is hidden behind the number.

**Acceptance Criteria:**

**Given** a live Deterministic Score
**When** a visitor opens its methodology page
**Then** the page states the formula, the exact XBRL concepts mapped to each formula input, and the formula version in use (FR-11, AD-5)
**And** it links to the model's original academic source (e.g. Piotroski 2000) (FR-11).

### Story 3.5: Deterministic cited explanation template (FR-12)

As a visitor,
I want a plain-language explanation generated directly from the computed results with citations,
So that I understand a score without any LLM inventing content.

**Acceptance Criteria:**

**Given** computed `score_results` and canonical facts
**When** a visitor requests an explanation
**Then** the explanation text is rendered by a deterministic template from the computed data, with no LLM in the loop (FR-12, AD-7)
**And** every explanation carries inline citations to the specific provenance record(s) it drew from (FR-12, AD-19)
**And** any statement that cannot be grounded in a citation is omitted (FR-12).

### Story 3.6: LLM constrained-rewrite layer (FR-12)

As a visitor,
I want the explanation optionally polished into fluent prose,
So that it reads naturally while staying strictly grounded.

**Acceptance Criteria:**

**Given** a correct deterministic explanation
**When** the LLM rewrite is enabled
**Then** it uses a small cheap model (default Claude Haiku 4.5) with the key from an env var, provider swappable (FR-12, AD-21)
**And** the LLM only rewrites/polishes already-correct text and never introduces a claim, number, or citation not already present (FR-12, AD-7)
**And** the LLM is never in the numeric/computation loop, and disabling it still yields a valid deterministic explanation (AD-7, AD-21).

---

## Epic 4: Discovery & Comparison

Wrap the complete company pages in a discovery shell and a session-scoped comparison. *(FR-1, FR-2, FR-13, FR-14; AD-8, AD-10.)*

### Story 4.1: Landing page starter list (FR-1)

As a visitor,
I want to see the Company Universe as explorable cards without logging in,
So that I can start exploring immediately.

**Acceptance Criteria:**

**Given** the current universe (CP, QSR, OTEX, SHOP)
**When** a visitor loads the landing page
**Then** all Phase-1 companies render as cards showing company name, ticker, and last-updated date, with no login required (FR-1)
**And** each card links directly to that company's overview page (FR-1).

### Story 4.2: Ticker search with honest coverage (FR-2)

As a visitor,
I want to search a ticker and get an honest result,
So that I'm never shown a fake or confusing outcome.

**Acceptance Criteria:**

**Given** the search input
**When** a visitor searches a ticker within the universe
**Then** they navigate to that company's overview page (FR-2)
**And when** a visitor searches a ticker outside the universe
**Then** they get an explicit "not yet covered" message via the `not_available` success envelope — never a silent failure, generic error, or fabricated result (FR-2, AD-10).

### Story 4.3: Add to comparison, session-scoped (FR-13)

As a visitor,
I want to add companies I've viewed to a comparison set,
So that I can line up candidates without an account.

**Acceptance Criteria:**

**Given** a company overview page
**When** a visitor adds it to comparison
**Then** the set persists only for the current browser session — no auth, no server-side persistence (FR-13, D4)
**And** the set allows a minimum of 2 and a maximum of 4 companies (FR-13).

### Story 4.4: Side-by-side comparison view (FR-14)

As a visitor,
I want to compare added companies' verdicts and scores in parallel,
So that I can decide between them with evidence.

**Acceptance Criteria:**

**Given** 2–4 companies in the comparison set
**When** a visitor opens the comparison view
**Then** it shows each company's Verdict and all currently-live lens scores in parallel columns (FR-14)
**And** it shows exactly the lenses live in the current phase for each company, consistent with the overview's phase honesty (FR-14, FR-9)
**And** differences beyond a stated threshold (e.g. diverging pass/fail signals) are visually highlighted (FR-14).

---

## Epic 5: Filing Change Detection & Quality-Lens Depth

First increment of the D9 decision workflow. Lawrence returns to a company after weeks away and sees exactly what moved, with both endpoints cited — then the two Quality/Health sub-metrics adopted under PRD OQ9 deepen the lens the change view reports on. *(FR-22, FR-5 extended; AD-6 supersession is the comparison source; AD-16 tri-state and AD-19 provenance bind throughout.)*

**Story order is deliberate:** 5.1 is a verification spike placed first because it is the only story in this epic whose outcome can change the epic's scope. Do not build 5.6 before 5.1 answers.

### Story 5.1: Debt-maturity coverage spike (live EDGAR verification)

As Lawrence (developer),
I want to know whether the debt maturity schedule is actually tagged for every filer in the universe, before any story assumes it,
So that debt maturity concentration is scoped from real coverage rather than from the existence of a tag name.

**Why this is a spike, not an implementation story.** `long_term_debt` is already canonical, but it is a single aggregate — maturity *concentration* needs the year-by-year schedule (due in year 1, 2, 3, 4, 5, thereafter). Under `us-gaap` those are standard tags (`LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths` and its YearTwo…AfterYearFive siblings) but they live in the debt footnote, which filers tag inconsistently. Under `ifrs-full` the equivalent is a liquidity-risk maturity analysis, typically expressed with **axis/member dimensions** rather than flat concepts — which the current canonicalization path may not handle at all. This is precisely the anti-pattern the project has been bitten by twice (the `shares_outstanding` dei bug, CP's PP&E tag switch): *never trust that a tag's existence means it covers the years you need.*

**Acceptance Criteria:**

**Given** live `data.sec.gov` company-facts access for all seven universe CIKs
**When** the spike completes
**Then** a written finding records, per filer and per fiscal year, whether a usable maturity schedule is present — not merely whether a tag name appears
**And** it states explicitly whether the IFRS filers' maturity analysis is reachable as flat facts or only as dimensional facts, and if dimensional, what canonicalization would have to change
**And** it recommends one of: proceed with Story 5.6 as specified / proceed with reduced scope (e.g. `us-gaap` filers only, IFRS `insufficient_data`) / drop the sub-metric and reopen OQ9 for it
**And** the finding is recorded in `sprint-status.yaml` with evidence, per the project's action-item convention.

### Story 5.2: Score-run diff engine

As the system,
I want to compute a structured diff between two non-superseded score runs for a company,
So that every later change-detection surface reads one deterministic, tested comparison rather than re-deriving its own.

**Acceptance Criteria:**

**Given** a company with at least two score runs under AD-6 supersession
**When** the diff engine compares a prior run to the current one
**Then** it returns changed canonical facts, changed signal statuses, changed band labels, and opened/resolved `data_quality_issues`, each carrying **both** endpoints with their provenance and accession numbers
**And** it reads only stored values — it never invokes `backend/scoring` or `backend/formulas` to produce a diff (deterministic boundary; also keeps the diff independent of formula-version drift)
**And** a band change is returned distinctly from an input change that left the band intact
**And** `insufficient_data` → a real value is classified as newly-available data, never as an improvement, and the reverse is classified as lost coverage, never as a decline
**And** a `mapping_version` or `formula_version` difference between the two runs is surfaced as a caveat on the diff, since a change may then reflect a rule change rather than a filing change
**And** no new mutable "previous value" column is introduced — supersession is the only source.

### Story 5.3: Change-detection read API

As the frontend,
I want an endpoint returning a company's changes since a given prior run or date,
So that the overview page can render "what changed" without computing anything.

**Acceptance Criteria:**

**Given** the diff engine from Story 5.2
**When** the endpoint is called for a ticker with an optional `since` parameter
**Then** it returns the structured diff, defaulting to the most recent prior run when `since` is omitted
**And** it stays read-only per AD-1 — no request can trigger scoring, ingestion, or recomputation
**And** a company with only one score run returns an explicit "no prior run to compare" state, distinct from both an error and an empty diff
**And** the response separates "no change since {date}" from "no data", so the UI can never render them identically.

### Story 5.4: "What changed" on the company overview

As Lawrence (investor),
I want to see what moved for a company since I last looked, with both values cited,
So that I can re-engage with a thesis without re-reading the whole page.

**Acceptance Criteria:**

**Given** a company with a computable diff
**When** Lawrence opens its overview page
**Then** a change summary shows each change as prior → current, each endpoint linking to its provenance record and accession number
**And** band crossings are visually distinguished from within-band input movements
**And** newly-available and newly-lost data are labelled as coverage changes, not as directional improvements or declines
**And** "no change since {date}" renders as an explicit statement, never as an empty region that could be mistaken for a failed load (this is the operational-honesty gap flagged in the 2026-08-02 assessment §3.17)
**And** a `mapping_version`/`formula_version` caveat from Story 5.2, when present, is shown rather than silently dropped.

### Story 5.5: Trajectory-over-level rules (OQ9)

As Lawrence (investor),
I want each Quality/Health signal to show its direction of travel, not only its current level,
So that a company improving from a weak base reads differently from one deteriorating from a strong one.

**Acceptance Criteria:**

**Given** a company with score runs across at least two fiscal years
**When** the Quality/Health lens renders
**Then** each applicable signal carries a trajectory classification derived deterministically from already-stored values, with the compared years stated
**And** trajectory is presented **alongside** the level, never as a replacement for it, and never blended with it into a composite
**And** a signal with insufficient history for a trajectory shows `insufficient_data` for the trajectory only, leaving its level intact (AD-16)
**And** the classification rule and its thresholds live in a versioned spec, labelled as a **ThesisTrace-authored** presentation rule and clearly distinguished from the original academic methodology — consistent with the standing rule that a caveat may annotate a score but never alter one.

### Story 5.6: Near-term debt share (OQ9) — *scoped by Story 5.1, 2026-08-04*

As Lawrence (investor),
I want to see how much of a company's debt comes due within twelve months relative to its total debt,
So that leverage reads as a timing risk and not only as a level.

**Scope was set by Story 5.1's live-EDGAR finding.** The originally-named "debt maturity concentration" is not buildable as specified — only QSR and CP carry a usable year-by-year ladder, and the three IFRS filers carry none at all for a structural reason (their maturity analysis is dimensional, and the company-facts API exposes only non-dimensional facts). The metric is therefore **redefined, not restricted**: near-term share is a single concept, identically defined whether read from a ladder's first bucket or from a current/noncurrent split, so it stays comparable across filers without a caveat. Full spike record: `engineering-findings.yaml`, `story_5_1_debt_maturity_spike`.

> **CORRECTED 2026-08-04 during implementation, by the live re-verification this story
> itself demanded.** The ACs below are the shipped ones. The original set was written on
> Story 5.1's premise that a maturity ladder's first bucket and a current-portion tag are
> the same concept and so need no caveat. Measured against real filed figures they are
> not: they differ in 11 of 15 shared years for CP (FY2013: 50M vs 189M), 10 of 10 for
> OTEX (FY2022: 168.9M vs 10.0M) and 2 of 12 for QSR. The ladder discloses undiscounted
> contractual principal; the current-portion tag is balance-sheet carrying amount.
>
> The ladder turned out to be unnecessary. Every filer that has one also tags the
> current/noncurrent split with equal or better coverage — including CP, which the spike
> reported as having none because it checked `LongTermDebtCurrent` and missed the
> `...AndCapitalLeaseObligationsCurrent` variant CP has tagged for 17 consecutive years.
> Using the split universally gives ONE measurement basis, which is what the original
> no-caveat goal actually required.

**Expected resolution** (live-verified 2026-08-04 at build time): CP FY2009–2025, QSR
FY2013–2025, OTEX FY2010–2025, BCE FY2016–2023, SU FY2016–2020 + FY2024–2025, CCJ
FY2017–2019 + FY2022–2025. 68 filer-years across 6 of 7 filers. SHOP does **not** resolve
— see the last AC.

**Acceptance Criteria:**

**Given** a filer with both a near-term debt figure and a total debt figure for a fiscal year
**When** near-term debt share is computed
**Then** it is derived deterministically from canonical facts, with its formula and threshold bands in a versioned spec labelled as a **ThesisTrace-authored** presentation rule, not an academic model
**And** both operands sit on ONE measurement basis — the balance-sheet carrying amount of long-term debt, split current/noncurrent — so the figure is comparable across filers with no caveat; maturity-ladder tags are **not** mapped at all, and a test asserts they never become so
**And** short-term borrowings (commercial paper, revolver draws, securitization) are excluded from **both** numerator and denominator, because their tag coverage is too filer-specific to include without summing an assumed subset; the spec states this limitation and it travels with every rendering of the figure
**And** `ifrs-full:Borrowings` is **not** used as a denominator: Suncor's includes short-term borrowings, verified live to equal its `ShorttermBorrowings` to the dollar in FY2016–2018, so all IFRS filers derive the total from the two halves instead
**And** a filer-year lacking either operand is `insufficient_data` — never estimated from the `long_term_debt` aggregate alone, never defaulted to zero (AD-16) — while a genuinely **filed** zero is a real value and displays as 0.0% (Cameco files exactly zero in FY2017, FY2019, FY2022 and FY2025)
**And** every new canonical concept is added with per-year live-verified coverage, and `MAPPING_VERSION` is bumped because a mapping rule genuinely changed (per `registry.yaml`'s procedure)
**And** the golden dataset is extended in the **same change** for every active company — including the two that resolve to `insufficient_data`, since SM-1 is a claim about the universe and a silent gap is what it exists to prevent
**And** SHOP is `insufficient_data` throughout: its numerator resolves from `ConvertibleDebtCurrent`, but `long_term_debt` is deliberately unmapped for SHOP (its convertible notes flip between the Current and Noncurrent tags near maturity), so the denominator has no second operand. Reversing that would move SHOP's hand-verified Piotroski and Beneish golden values and belongs in its own change.

### Story 5.7: Maturity profile detail for filers that support it — *enrichment, not a metric*

As Lawrence (investor),
I want to see the full year-by-year repayment schedule where a filer actually publishes one,
So that I can distinguish a smooth maturity ladder from a cliff.

**Acceptance Criteria:**

**Given** a filer with a usable multi-year ladder (currently QSR FY2014–2024 and CP, with CP's "thereafter" only from FY2022)
**When** its Quality/Health lens renders
**Then** the year-by-year profile is shown as supplementary detail beneath near-term share
**And** a filer without a ladder shows **no gap, blank, or "missing" affordance** — the profile is absent for most of the universe by structure, and rendering it as missing data would misrepresent five of seven filers as deficient
**And** where the "thereafter" bucket is absent for a year, the profile states that it is truncated rather than implying the displayed buckets are the whole debt
**And** this story ships **after** 5.6 and may be deferred indefinitely without blocking the epic — it is presentation depth for two filers, not a lens capability.

---

## Epic 6: Narrow Valuation — Reverse DCF

Lawrence sees what growth the *current market price* implies for a company, with every assumption explicit and a sensitivity range — never a bare fair-value point estimate. Deliberately a narrow slice of FR-16, not the full Value lens: reverse DCF only, because it answers "is the price reasonable?" while making the model's assumptions the visible output rather than hiding them behind a single number.

**Decomposed 2026-08-06.** Story 6.1's spike answered the data question: the inputs are reachable for 6 of 7 filers. What remained were five product decisions, which are recorded below as **assumptions rather than findings** — each is a judgement call, each is reversible, and each should be challenged before the story that depends on it is built.

> **A-1 — Horizon: five explicit years plus a terminal value.** Ten explicit years implies a precision nobody has, and most filers carry only 9–14 years of history, so a ten-year forecast extrapolates further than the record supports.
>
> **A-2 — Terminal value: perpetuity growth, not an exit multiple.** An exit multiple imports a peer comparable, which is a second source of truth ThesisTrace does not have and would sit awkwardly beside the "never blend into a composite" discipline. Perpetuity growth is one explicit assumption the reader can see and argue with.
>
> **A-3 — Discount rate: user-supplied, with a stated default.** WACC needs beta and an equity risk premium, neither of which is in EDGAR and both of which are judgements. Computing one would make ThesisTrace originate the single most consequential assumption in the model and present it as derived. The epic's own promise is that assumptions are the visible output — so this one is an input.
>
> **A-4 — Solve backward for implied revenue growth, holding operating margin at its trailing level.** Growth is the assumption investors most often over-extrapolate, and it is the one ThesisTrace can check against something it already holds deterministically: the filer's own 9–24 years of revenue history. Solving for margin instead would produce a number with no comparable.
>
> **A-5 — Sensitivity across discount rate × terminal growth.** These two move a DCF most and are least observable. Revenue growth cannot be an axis because it is the output.

**FRs covered:** FR-16 (partial — reverse DCF only)

### Story 6.1: Reverse-DCF input coverage spike

As Lawrence (developer),
I want to know which reverse-DCF inputs are actually reachable for each filer before any story assumes them,
So that the metric is scoped to what the data supports rather than redefined mid-build.

**Acceptance Criteria:**

**Given** the seven-filer universe
**When** coverage is checked against ingested raw facts, and live company-facts wherever local history is suspect
**Then** per-filer, per-year coverage is recorded for every candidate input, not merely tag presence
**And** any filer that cannot support the metric is named, with the structural reason
**And** every finding is recorded as a hypothesis to be re-confirmed at build time, per Story 5.1's precedent
**And** the record states what the spike could **not** establish.

*Status: DONE 2026-08-06. Findings in `engineering-findings.yaml` → `story_6_1_reverse_dcf_coverage_spike`. Verdict: reachable for 6 of 7; Suncor tags no PP&E purchase flow and must read `insufficient_data`.*

### Story 6.2: Free-cash-flow canonical concepts — interest classification decided

As the system,
I want free cash flow assembled from canonical concepts that mean the same thing in both reporting regimes,
So that an implied growth rate computed for Cameco is comparable with one computed for CP.

**The decision this story exists to force.** Free cash flow is `cash_from_operations − capex`, and both operands are available. But **`cash_from_operations` is not comparable across regimes as filed**: US GAAP mandates interest paid inside operating activities, while IAS 7 permits operating *or* financing. Two filers with identical economics can therefore report different CFO. This is the same shape as D8 consequence 3, where IFRS's absent operating-profit line forced an explicit `ebit` derivation — and it must be settled in the versioned spec, not in a mapping row.

**Acceptance Criteria:**

**Given** the `us-gaap` and `ifrs-full` taxonomies
**When** the new concepts are mapped
**Then** `capex` and `cash_and_equivalents` exist as canonical concepts with per-year coverage verified live, never inferred from tag presence
**And** `capex` maps `PaymentsToAcquirePropertyPlantAndEquipment`, OTEX's `PaymentsToAcquireProductiveAssets` variant, and the `ifrs-full` purchase tag — and does **not** map QSR's `CapitalExpendituresIncurredButNotYetPaid`, which is an accrual disclosure rather than cash capex
**And** `cash_and_equivalents` excludes restricted cash, because restricted cash cannot service debt; the two tags are recorded as distinct concepts and QSR's mid-history switch between them is handled by per-year coverage, not by treating them as equivalent
**And** each filer's actual interest classification is verified live, and where a filer places interest in financing the run is annotated `computed_with_caveat` with the reason stored as data — reusing the existing caveat mechanism rather than inventing one
**And** `MAPPING_VERSION` is bumped to `concepts_v8` per AD-2, and no spec an existing stored version points at is edited
**And** Suncor resolves no `capex` and is therefore `insufficient_data` for the whole epic — substituting its intangibles-additions tag is explicitly rejected, being a partial base against a full one, the same error the QSR gross-profit re-verification refused.

### Story 6.3: Versioned reverse-DCF spec and deterministic solver

As the system,
I want the reverse DCF expressed as a versioned ThesisTrace specification and solved deterministically,
So that the implied growth rate is reproducible and every judgement in it is published rather than buried in code.

**Acceptance Criteria:**

**Given** a filer-year with free cash flow, market capitalisation, total debt and cash
**When** the solver runs
**Then** enterprise value is `market cap + total_debt − cash_and_equivalents`, each operand citable
**And** the solver returns the constant five-year revenue growth rate (A-1) that equates the discounted free-cash-flow stream plus a perpetuity terminal value (A-2) to enterprise value, holding operating margin at its trailing level (A-4)
**And** the spec is `thesistrace_presentation_rule`-kind, carries `spec_version`, and states in a machine-readable field — not a comment — that the horizon, terminal method, discount-rate treatment and solve-target are ThesisTrace's choices and not a published academic model
**And** the discount rate is an input with a declared default (A-3), and the default's value and origin are published on `/methodology`
**And** every figure is `Decimal`, never float (AD-15)
**And** where the solver cannot converge, or an operand is absent, the result is `insufficient_data` with the reason — never a clamped, defaulted or extrapolated value
**And** the solver never returns a fair-value point estimate, and a test asserts no such field is exposed, mirroring the maturity profile's no-total guard.

### Story 6.4: Sensitivity range over discount rate and terminal growth

As Lawrence (investor),
I want the implied growth rate shown as a range across the two assumptions that move it most,
So that I read it as a band of plausibility rather than a single number that looks like a fact.

**Acceptance Criteria:**

**Given** a filer-year the solver resolves
**When** the sensitivity is computed
**Then** the implied growth rate is solved across a declared grid of discount rate × terminal growth (A-5), with the grid's bounds and step declared in the spec
**And** the rendered output leads with the range, not the midpoint
**And** a cell that fails to converge is shown as such rather than omitted, so the grid cannot silently misrepresent its own coverage
**And** the grid is computed deterministically in Python and stored, so a read cannot trigger computation (AD-1).

### Story 6.5: Implied-assumptions read API

As the frontend,
I want the implied growth rate, its sensitivity grid, and every operand behind it in one response,
So that the page can show the reader how the number was reached without a second round trip.

**Acceptance Criteria:**

**Given** a company with a resolved reverse DCF
**When** the overview is requested
**Then** the response carries the implied growth rate, the sensitivity grid, the discount rate used, and each operand — free cash flow, market cap, total debt, cash — with provenance (AD-19)
**And** every operand is independently recomputable from the response, closing risk-assessment finding 3.5 for this feature
**And** the response states the filer's own historical revenue CAGR over its available history alongside the implied rate, because the comparison is the point of A-4
**And** the historical window adapts to the filer's actual coverage and is labelled with it — no fixed decade promise, since IFRS filers start ~FY2017
**And** the query folds into the existing single-pass overview read rather than adding round trips (AD-1).

### Story 6.6: Reverse DCF on the company overview

As Lawrence (investor),
I want the implied growth rate presented beside what the company has actually achieved,
So that I can judge whether the price is asking for something the business has ever done.

**Acceptance Criteria:**

**Given** a company whose reverse DCF resolves
**When** the company page renders
**Then** the implied growth rate appears with its sensitivity range and the discount rate that produced it, all visible without interaction
**And** the filer's own historical revenue CAGR is shown adjacent, labelled with the window it covers
**And** the assumptions are labelled as ThesisTrace's, distinctly from the four academic models, so the page cannot read as though a published model produced them
**And** a filer that cannot resolve — Suncor — shows `insufficient_data` with its reason, following AD-16 rather than the maturity profile's render-nothing exception, because this is a lens capability rather than supplementary disclosure detail
**And** custom visualisation only; no off-the-shelf charting library
**And** the page is verified in a browser against real `concepts_v8` data before the story closes — the standing rule, which found four defects in Story 5.4 and two more in 5.7.

### Story 6.7: Golden-dataset coverage for the implied growth rate

As Lawrence (developer),
I want the implied growth rate hand-verified for every filer that resolves it,
So that SM-1 continues to hold over the capability, not only over the four academic models.

**Acceptance Criteria:**

**Given** the filers that resolve a reverse DCF
**When** the golden dataset is extended
**Then** each expected implied growth rate is computed independently, without importing `backend/scoring`, `backend/formulas` or the solver itself — the constraint that let the IFRS golden pass catch its own averaging error
**And** every operand is compared, not only the final rate, because two wrong operands can agree on an aggregate
**And** Suncor's `insufficient_data` and its reason are asserted, so its absence can never later be mistaken for a coverage bug
**And** the golden entries are added in the **same change** as the capability — SM-1 is a claim about the universe, and shipping the feature first would silently break it

## Epic 10: Report-Style Company Page

Decomposed 2026-08-27 under **D12**. Presentation-only: every story re-presents figures the
pipeline already computes; no story may add ingestion, computation or a new figure without
leaving D12's cover (at which point D9 applies).

### Story 10.1: Report shell, section navigation and dark-first theme

As Lawrence (investor),
I want the company page organized as a navigable, sectioned report,
So that reading a company feels like working through a structured dossier rather than scrolling a feed.

**Acceptance Criteria:**

**Given** a company page
**When** it renders
**Then** content is organized into sections — Overview, Valuation, Past Performance, Financial Health, Integrity & Evidence — with a persistent section nav that tracks scroll position, and each section addressable by a stable URL anchor
**And** dark becomes the primary theme using `DESIGN.md`'s existing dark tokens, with light mode retained and both themes rendering correctly
**And** every existing capability (Verdict, what-changed, reverse DCF, debt cards, provenance popovers, comparison, methodology links) remains reachable — this story moves furniture, it removes nothing, asserted by the existing frontend tests passing unmodified
**And** the page is verified in a browser on filers chosen by which code paths they exercise, per the live-data DoD — not by convenience

### Story 10.2: Verdict constellation — the four-model hero glyph

As Lawrence (investor),
I want one custom visual at the top showing each model's verdict on its own labelled axis,
So that I get the at-a-glance read a snowflake gives without a blended score.

**Acceptance Criteria:**

**Given** a company with stored score runs
**When** the Overview section renders
**Then** an original radial glyph shows one axis per model — Piotroski, Altman, Beneish, Sloan — each individually labelled and coloured by its own band vocabulary, carried as per-model data rather than a shared enum (the `bandTone` lesson)
**And** the axes are never filled into a single polygon area, and no aggregate number, shape or grade summarizing multiple models appears anywhere on the glyph (D12 guard 1 — the Verdict decision applied to pixels)
**And** a model with `insufficient_data` or an exclusion renders that state explicitly on its axis per AD-16, never as a zero-length or empty axis that reads as a bad score
**And** clicking an axis navigates to that model's section of the report
**And** the glyph is original work, visually distinct from Simply Wall St's design-patented snowflake — custom SVG, no off-the-shelf charting (D7)
**And** verified in a browser in both themes before the story closes

### Story 10.3: Rewards and risks derived from computed signals

As Lawrence (investor),
I want a rewards-vs-risks summary at the top of the report,
So that the strongest computed positives and negatives are readable in ten seconds with the evidence one click away.

**Acceptance Criteria:**

**Given** a company's stored signal states, bands, caveats and open data-quality issues
**When** the Overview renders
**Then** a rewards list and a risks list appear, each bullet produced by a versioned deterministic rule that maps existing computed states to fixed sentences — spec data with a published `rationale`, never free prose and never an LLM (the `derivations_v2`/`trajectory_v1` lesson: user-visible rationale is a published field)
**And** each bullet cites the figure that produced it and links to the section where that figure lives
**And** no bullet originates a new figure, threshold or judgment — selection and wording are the spec's own, labelled as ThesisTrace's, distinct from the four academic models
**And** a company with no qualifying states shows an honest empty state, never padded bullets
**And** the rule spec declares its inputs and a test asserts declared ⊇ actually-read (the `piotroski_v1` inputs lesson)

### Story 10.4: Fundamentals summary and earnings waterfall

As Lawrence (investor),
I want a big-figure fundamentals block and an income waterfall,
So that the scale and shape of the business are visible before the forensic detail.

**Acceptance Criteria:**

**Given** canonical facts for the latest complete fiscal year
**When** the Overview renders
**Then** a fundamentals block shows headline figures (revenue, earnings, and market value where price data exists) with compact formatting in which every gate tests the integer count of the unit its branch renders (the `compactAmount` boundary lesson)
**And** a revenue → cost → gross profit → other → earnings waterfall renders from canonical facts only, as a custom visualization
**And** a filer whose taxonomy lacks a component degrades honestly — CP has no COGS, a by-nature IFRS filer has no SG&A — the affected bar is absent with its stated reason, never rendered as zero
**And** every figure carries provenance to its accession number
**And** verified in a browser on CP and one by-nature IFRS filer, chosen because they exercise the missing-component path

### Story 10.5: Report sections — valuation, performance, health, integrity

As Lawrence (investor),
I want the existing capabilities re-homed into their report sections,
So that each research question — is the price reasonable, what changed, is it healthy, can I trust the numbers — has one place to be answered.

**Acceptance Criteria:**

**Given** the existing overview capabilities
**When** the restructure lands
**Then** reverse DCF and its sensitivity range live under Valuation; what-changed and trajectory under Past Performance; Altman, Piotroski and the debt cards under Financial Health; Beneish, Sloan and data-quality issues under Integrity & Evidence
**And** no computation, API contract or figure changes — presentation-only, asserted by the backend test suite passing unmodified
**And** each section states its own data freshness (latest score run and filing date it reflects)
**And** every state variant of each capability (resolved, `insufficient_data` with reason, caveat, exclusion) renders correctly in its new home
**And** verified in a browser across filers chosen to exercise every section variant

### Story 10.6: Provenance and freshness footer

As Lawrence (investor),
I want the report to end with what the data is and when it last moved,
So that the report's honesty is inspectable in one place.

**Acceptance Criteria:**

**Given** a rendered company report
**When** the footer renders
**Then** it states the data sources actually used for this filer (EDGAR company facts; Tiingo close; Bank of Canada FX where the filer reports in CAD), the latest accession number and its filing date, the last pipeline run, and the mapping and formula-spec versions in force
**And** every statement is read from stored data — nothing in the footer is hardcoded
**And** a source the filer does not use is absent, not listed generically
**And** verified in a browser

### Story 10.7: Full-universe browser verification

As Lawrence (developer),
I want the finished report rendered for every universe filer in both themes,
So that the redesign cannot ship verified only against the filers it happened to be built on.

**Acceptance Criteria:**

**Given** the completed Epic 10 stories
**When** the closing verification runs
**Then** every universe filer's page is rendered in a real browser in both light and dark themes, and the results are recorded in `engineering-findings.yaml`
**And** the filers examined in detail are chosen by code path — missing-component, `insufficient_data`, caveat, exclusion, and IFRS derived-concept variants — the Story 6.6 lesson that a spot-check covers only the paths its subjects exercise
**And** any defect found is fixed or explicitly recorded before the epic closes
**And** corrupting an expected value fails the suite, confirming the guard bites.

## Epic 11: UI Redesign — Instrument Panel

Re-skins Epic 10's report shell to the Instrument Panel direction chosen from a five-way design
exploration (2026-08-28): JetBrains Mono, a muted amber accent, terminal-precision density, and
click-to-expand inline definitions on every jargon term as the answer to Lawrence's "don't just
throw numbers at the user" concern. Presentation-layer only (AD-8) — no story in this epic may
change a score, a formula, an API contract, or a stored figure. The two reference mockups
(`https://claude.ai/code/artifact/7a68fd99-e188-4b4e-95ca-934000769e68`, extended to cover the
full report) are direction-setting references, not source to copy verbatim — they use an inverted
token structure (bare `:root` = light) because they were built standalone; the real app keeps its
own existing convention (bare `:root` = dark, per D12, with `:root[data-theme="light"]` as the
explicit opt-in) and re-skins the *values*, not the structure.

### Story 11.1: Design-token migration to the Instrument Panel palette

As Lawrence (investor learning through the tool),
I want the design tokens re-skinned to the Instrument Panel palette and typography,
So that every component built on top of them inherits the new direction automatically instead of
each story reinventing colors.

**Acceptance Criteria:**

**Given** `frontend/app/globals.css`'s existing Tailwind v4 `@theme` token layer
**When** this story lands
**Then** `--font-sans`/`--font-mono` are replaced with JetBrains Mono as the primary read face (loaded via the Google Fonts `<link>` pattern already used for Inter, with a real monospace fallback stack), and `--color-brand-*` moves to the muted amber family
**And** the existing bare-`:root`-is-dark / `:root[data-theme="light"]` structure is preserved unchanged — only the hex values move, matching D12's convention rather than the standalone mockup's inverted one
**And** all five signal states — `pass`, `fail`, `caveat`, `pending`, `excluded` — keep distinct, contrast-safe colors in both themes; `excluded` (currently purple) is not dropped just because the mockup exploration never rendered it (it is real, structurally-unreachable-but-coded product state, not decoration)
**And** the named type scale (`--text-display`…`--text-caption`) and radius/shadow tokens are re-tuned for the terminal-density aesthetic (tighter line-height, sharper corners) rather than left at their SaaS-dashboard defaults
**And** both themes are verified in a browser side by side before this story closes — token work is invisible until something renders it, so a second, throwaway component is an acceptable way to check contrast, not a reason to skip the check

### Story 11.2: Core UI primitives

As Lawrence (investor learning through the tool),
I want the shared primitives — `Badge`, `Card`, `Button`, `Gauge`, `CitationChip`, `TrajectoryChip`,
the icon set — rebuilt on the new tokens,
So that every screen built from them is consistent by construction, the same way the current
SaaS-dashboard look is.

**Acceptance Criteria:**

**Given** the Story 11.1 token layer
**When** each primitive in `frontend/app/components/ui/` is migrated
**Then** every existing variant/prop each component currently supports still exists and still maps to the same semantic meaning (a `Badge variant="fail"` still means fail) — this story restyles, it does not change any component's public interface, asserted by existing frontend tests passing unmodified
**And** `Gauge` is redrawn to the terminal-precision visual language (the mockup's flat readout-row treatment, not a rounded-pill gauge) while keeping its band-boundary math untouched
**And** `CitationChip`'s expand-to-provenance interaction is preserved exactly — this story changes its skin, not its behavior
**And** every primitive renders correctly in both themes

### Story 11.3: Report shell and navigation

As Lawrence (investor learning through the tool),
I want the page shell, section nav, and theme toggle re-skinned,
So that the report reads as one coherent terminal document from the header down, not a redesigned
interior inside old chrome.

**Acceptance Criteria:**

**Given** `frontend/app/layout.tsx`, `ReportNav.tsx`, and `ThemeToggle.tsx`
**When** this story lands
**Then** the persistent scroll-tracking section nav (Story 10.1) keeps its exact tracking behavior, restyled to the terminal aesthetic (the mockup's `// SECTION` label convention is a reasonable reference, not mandatory)
**And** `ThemeToggle` continues to set `data-theme` on `<html>` exactly as it does today (Story 11.1 changed only the values that attribute selects between) and the server-side cookie read that prevents a flash-of-wrong-theme is unaffected
**And** the ticker/company header block adopts the new type scale
**And** verified in a browser in both themes on at least one filer before closing

### Story 11.4: Overview — Verdict glyph, Fundamentals, Rewards & Risks

As Lawrence (investor learning through the tool),
I want the Overview section's hero content re-skinned,
So that the first thing the report shows already reads in the new direction.

**Acceptance Criteria:**

**Given** `VerdictGlyph.tsx`, `Fundamentals.tsx`, and `RewardsRisks.tsx`
**When** this story lands
**Then** the four-model glyph keeps every D12 guard intact — one axis per model, each carrying its own band vocabulary as data (the `bandTone` lesson), never filled into a single polygon, no aggregate number/shape/grade anywhere on it — restyled to the new palette, not redesigned in shape or logic
**And** the SVG continues to use a `title` *attribute*, never a `<title>` child element, per the Story 10.2 hydration-mismatch lesson already fixed once in this component
**And** the Fundamentals waterfall and Rewards & Risks cards adopt the new visual language while every existing degradation path (missing-component, honest-empty-state) still renders correctly
**And** verified in a browser on a filer that exercises at least one `insufficient_data` axis and one missing-component fundamentals gap, not just a fully-covered filer

### Story 11.5: Inline term-definition component (new capability)

As Lawrence (investor learning through the tool),
I want jargon and signal terms to expand inline into a plain-language definition when clicked,
So that reading a report doesn't require knowing the vocabulary before I start, and I don't lose
my place jumping to a glossary page.

**Acceptance Criteria:**

**Given** a signal key, model term, or other jargon rendered anywhere in the report
**When** it is marked as a definable term
**Then** it renders with the underlined-amber-term treatment from the mockup, and clicking it expands a definition inline (no navigation, no page jump) and collapses on a second click
**And** definitions are a versioned, spec-owned dataset (one definition per term, keyed consistently — e.g. co-located with or adjacent to `SIGNAL_LABEL` in `page.tsx`, or promoted to its own spec file if the term list grows past what a page-local map should hold), never free text generated at render time — this is presentation content, not an LLM output, per AD-8
**And** the component is a single reusable primitive (not duplicated per section) so Story 11.7 can wire it into every signal table without reimplementing the interaction
**And** keyboard-accessible (focusable, expandable via Enter/Space, not click-only) and respects `prefers-reduced-motion` for the expand transition
**And** at least the sub-signal keys already listed in `page.tsx`'s `SIGNAL_LABEL` map have real definitions before this story closes — not placeholders

### Story 11.6: Valuation and Past Performance

As Lawrence (investor learning through the tool),
I want the Valuation and Past Performance sections re-skinned,
So that the reverse-DCF assumptions and the what-changed narrative read in the same terminal
language as the rest of the report.

**Acceptance Criteria:**

**Given** `ReverseDcf.tsx` and `WhatChanged.tsx`
**When** this story lands
**Then** both re-skin cleanly with no change to the data they render or the deliberate visual separation between ThesisTrace's own reverse-DCF assumptions and the four published models (Story 6.6's separation stays intact — same section, still visually distinct from the Verdict grid)
**And** any jargon in these sections (e.g. "implied growth rate", "terminal value", "sensitivity range") is wired into the Story 11.5 inline-definition component, not left unexplained just because it lives outside the four-model signal tables
**And** verified in a browser on a filer whose reverse DCF resolves and one whose it does not (the `insufficient_data` / no-year-resolves state)

### Story 11.7: Financial Health, Integrity & Evidence, and the provenance footer

As Lawrence (investor learning through the tool),
I want the four model cards, the debt cards, and the closing provenance footer re-skinned and
wired to the new inline-definition component,
So that the densest, most jargon-heavy part of the report is exactly where the teaching mechanism
does the most work.

**Acceptance Criteria:**

**Given** the Financial Health and Integrity & Evidence sections (model cards, `NearTermDebtShare.tsx`,
`MaturityProfile.tsx`, the data-quality warning block, `ProvenanceFooter.tsx`)
**When** this story lands
**Then** every sub-signal key in every model's expanded `<details>` breakdown uses the Story 11.5
inline-definition component (this is the section the mockup's own reference build proved the
mechanism against — Piotroski's nine signals — extend that pattern to Altman, Beneish, and Sloan's
signal sets)
**And** the data-quality warning block and provenance footer re-skin without changing what they
assert — every footer statement remains read from stored data, nothing hardcoded (Story 10.6's
guarantee)
**And** verified in a browser on a filer that exercises a caveat state (e.g. BCE's derived-concept
citations) and one that exercises an open data-quality warning

### Story 11.8: Full-universe browser verification

As Lawrence (developer),
I want the redesigned report rendered for every universe filer in both themes,
So that the redesign cannot ship verified only against the filers it happened to be built and
screenshotted on — the same closing discipline Epic 10 applied to itself in Story 10.7.

**Acceptance Criteria:**

**Given** the completed Epic 11 stories
**When** the closing verification runs
**Then** every universe filer's page is rendered in a real browser in both light and dark themes,
and the results are recorded in `engineering-findings.yaml`
**And** the filers examined in detail are chosen by code path per the Story 6.6 lesson — at minimum
one missing-component filer, one IFRS derived-concept filer, one filer with an open data-quality
issue, and one filer whose reverse DCF does not resolve — not by convenience
**And** the inline-definition component (Story 11.5) is specifically exercised on at least one term
per model to confirm the expand/collapse interaction survives real content, not just the mockup's
fixed example
**And** any defect found is fixed or explicitly recorded before the epic closes
**And** the existing backend and frontend test suites pass unmodified — this epic is presentation-only
by definition, and a test needing to change would mean that boundary was crossed

### Story 11.9: Methodology pages — model-level explainers and worked examples

As Lawrence (investor learning through the tool),
I want each model's `/methodology/[model]` page to explain *why* the score works, not just what it
computes, with a worked example against a real filer,
So that the report teaches the four models instead of assuming I already know them — the gap
Story 11.5's signal-level definitions don't close, because "net income ÷ total assets is positive"
explains a mechanic, not why financial strength shows up that way in the first place.

**Acceptance Criteria:**

**Given** `frontend/app/methodology/[model]/page.tsx` and the `/api/methodology/{model}` payload
(which already carries `description`, per-signal `description`s, `bands.citation`, `source`, and
`derivations` — Story 11.9 adds narrative content, not a new API field)
**When** this story lands
**Then** each of the four pages gains a "why this works" explainer in plain language — the
intuition the model is built on (e.g. Beneish: a manipulated earnings figure tends to leave
statistical fingerprints across receivables, margins, and accruals simultaneously, which is why it
takes eight signals rather than one) — grounded in and citing the model's own primary source, not
a secondary summary
**And** each page includes one worked example computed from a real universe filer's actual stored
signals — deriving the aggregate score step by step from real values (the mockup's "Journal"
direction already proved this pattern live against QSR's Piotroski 6.0; extend the same technique
to Altman, Beneish, and Sloan)
**And** any jargon in the new explainer or worked-example text reuses the Story 11.5
inline-definition component rather than introducing a second, inconsistent glossary mechanism
**And** every claim about *why* a model works is verified against the model's own primary paper
before publishing — secondary sources (blog posts, explainer sites) may inform tone and structure
but never supply a mechanical claim unverified, per the project's standing rule that a cited claim
is only as good as the source it names
**And** the Beneish five-variable coefficient question already on record as OPEN (`research-beneish-five-variable-model.md`
— whether the published `0.107` coefficient belongs to DEPI or TATA) is not silently resolved by
this story picking one reading for the explainer text; if the five-signal model is in scope for this
page at all, the ambiguity is stated as ambiguous, not smoothed over for readability
**And** verified in a browser for all four models before this story closes

---

## Epic 12: US Universe Expansion — Campbell's & Zoetis

Onboard CPB and ZTS, both plain `us-gaap` 10-K filers, driven by Lawrence's real, staked decision
to buy each (decision packets `_bmad-output/decision-packets/2026-09-01-CPB.md` and
`2026-09-01-ZTS.md`, section 1 written before ingestion, per D11). Live-verified 2026-09-01 against
`data.sec.gov`: under the current `us-gaap_v8` mapping CPB's revenue coverage is FY2017-2025 and
ZTS's is FY2016-2025. ZTS's legacy `SalesRevenueNet` matches `Revenues` in FY2016-2017 and explains
the FY2014 gap, but that fallback is not yet in the mapping. CPB's `SalesRevenueGoodsNet` differs
from continuing-operations `Revenues` and remains rejected pending basis reconciliation. ZTS's
restricted-inclusive cash tag also requires issuer-specific handling because its 2019 10-K discloses
restricted cash after the tag switch. This is universe growth under an already-supported taxonomy —
the same shape as Epic 1's original onboarding and D8's IFRS track — not a new capability, so D9's
gate does not apply; D11 is the governing decision, and the two decision packets are its evidence.

### Story 12.1: Live EDGAR concept-coverage spike for Campbell's and Zoetis

As Lawrence (developer),
I want every concept the four models and the reverse-DCF solver actually read — not just
revenue — checked for live, per-year coverage against real `data.sec.gov` company-facts for both
filers,
So that a coverage gap is caught as a spike finding before ingestion, not discovered later as a
silent `insufficient_data` that looks like a bug.

**Acceptance Criteria:**

**Given** the full input list each formula spec declares (Piotroski's 9 inputs, Altman's 5, Beneish's
8, Sloan's accrual inputs, the reverse-DCF's free-cash-flow and debt-schedule operands — the same
list `scoring/runner.py` already enforces per-model)
**When** this spike runs against CPB's and ZTS's live EDGAR company-facts JSON
**Then** each concept's fiscal-year coverage is recorded per filer, bucketed on `end` (fact period),
never on EDGAR's `fy` (filing year) — the same rebucketing this project has needed for every prior
filer addition
**And** ZTS's single-year revenue gap at FY2014 (found in the 2026-09-01 live check) is explained —
either a genuine tag switch (a second tag covers FY2014, per the pattern already resolved for other
filers) or a real, permanent coverage gap that must be declared `insufficient_data` for that year
**And** any tag whose name suggests a concept but whose semantics differ (accrual vs. cash,
inclusive vs. exclusive) is checked against the filer's own filed values before being mapped, per
the recurring "a tag whose name contains the concept is often not the concept" lesson
**And** findings are recorded in `engineering-findings.yaml` under `story_12_1_coverage_spike`,
including per-concept per-year tables for both filers, before Story 12.2 begins

### Story 12.2: EDGAR ingestion for Campbell's and Zoetis

As Lawrence (developer),
I want CPB's and ZTS's real EDGAR filings ingested into `raw_facts` using the existing `us-gaap`
ingestion path,
So that both filers' historical facts are available for canonicalization, exactly as CP, QSR,
OTEX and SHOP already are.

**Acceptance Criteria:**

**Given** the existing EDGAR ingestion pipeline (`backend/ingestion/`) and Story 12.1's coverage
findings
**When** ingestion runs for CIK 0000016732 (CPB) and CIK 0001555280 (ZTS)
**Then** both issuers and their filings (10-K, and 10-K/A where one exists) are created with
correctly attributed `fiscal_year_end` (CPB's non-calendar FYE — early August — handled the same
way OTEX's June 30 FYE already is)
**And** the `dei` cover-page-date exclusion and full-year-duration filtering already fixed for
every prior filer's fiscal-year-end determination apply unchanged — no new fiscal-year bucketing
logic is written for these two filers
**And** ingestion is idempotent — re-running it does not duplicate `raw_facts` rows, matching the
pattern already established for the other seven filers

### Story 12.3: Canonicalization and validation for Campbell's and Zoetis

As Lawrence (developer),
I want CPB's and ZTS's raw facts canonicalized and validated under the existing `us-gaap` mapping
spec,
So that both filers produce canonical facts and any accounting-identity data-quality issues on the
same terms as the rest of the universe.

**Acceptance Criteria:**

**Given** Story 12.1's per-concept coverage findings and the existing `us-gaap` concept-mapping
spec
**When** `canonicalize_issuer` and `run_validation` run for both filers
**Then** any tag-switch or filer-specific mapping need surfaced by Story 12.1 is added to the
mapping spec as a versioned entry with a `note` explaining the choice — never resolved silently in
code
**And** any genuine accounting-identity violation opens a `data_quality_issues` row per AD-3/AD-16
— never silently guessed or defaulted
**And** a concept with no live coverage for a given year renders `insufficient_data` for that
filer-year, never an assumed zero (AD-16)

### Story 12.4: Golden-dataset coverage for Campbell's and Zoetis

As Lawrence (developer),
I want CPB's and ZTS's scores hand-verified against real EDGAR data and added to
`phase1_golden.yaml` across all four models and the reverse-DCF implied growth rate,
So that SM-1's golden-dataset guarantee — reopened by every universe addition — holds for the two
new filers, not just the five test scenarios already in place.

**Acceptance Criteria:**

**Given** the golden-dataset harness pattern already used for the other seven filers
**When** golden entries are added for CPB and ZTS
**Then** each entry's expected value is hand-computed independently, without importing
`backend/scoring`, `backend/formulas` or the solver — the same independence that caught the
IFRS golden dataset's own averaging error
**And** the golden fixture is confirmed to actually carry the tags each new entry exercises before
the entry is written, per the standing "fixture is a trimmed subset" lesson — an entry a fixture
cannot reproduce is deleted or reworked, not left in place asserting nothing
**And** corrupting an expected value is confirmed to fail the suite, for at least one entry per
filer, before this story closes

### Story 12.5: Scheduled pipeline inclusion and full-universe browser verification

As Lawrence (investor),
I want CPB and ZTS to appear in the nightly scheduled pipeline and render correctly on every
existing page (overview, report, methodology, comparison),
So that both filers are genuinely part of the universe, not just present in the database.

**Acceptance Criteria:**

**Given** the scheduled pipeline (`pipeline/run.py`) and the full set of existing pages
**When** CPB and ZTS run through a full nightly cycle
**Then** both appear on the landing page, ticker search, and comparison view alongside the
existing seven filers
**And** both are rendered live in a browser across the report page's every section (Verdict glyph,
Rewards & Risks, Valuation, Past Performance, Financial Health, Integrity & Evidence) and the
methodology pages — chosen as spot-check subjects specifically because they exercise a plain
`us-gaap` non-calendar (CPB) and calendar (ZTS) fiscal-year-end path, not because they are
convenient
**And** any defect found is fixed or explicitly recorded in `engineering-findings.yaml` before
this epic closes
**And** `data_quality_issues` for both filers, if any, are reviewed and dispositioned (resolved or
explicitly accepted with a reason), never left open and unexamined
