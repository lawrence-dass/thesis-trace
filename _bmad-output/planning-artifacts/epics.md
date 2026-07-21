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
