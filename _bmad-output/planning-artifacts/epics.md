---
stepsCompleted: [step-01-validate-prerequisites, step-02-design-epics]
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
