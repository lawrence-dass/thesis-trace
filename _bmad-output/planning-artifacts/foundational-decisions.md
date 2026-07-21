# ThesisTrace — Foundational Decisions

**Date:** 2026-07-17
**Status:** Locked (revisit only via explicit correct-course)
**Input:** LedgerLens/Fundalens consolidation review (`_bmad-output/planning-artifacts/ledgerlens-fundalens-consolidation-review.md`, copied into the repo 2026-07-20 from its original location outside version control)

## D1 — Product name: ThesisTrace

One consolidated evidence-backed equity intelligence platform, replacing the separate LedgerLens and Fundalens concepts. The name encodes the product promise: every investment thesis traceable to evidence.

## D2 — Primary user

**The diligence-driven retail investor** — someone practicing value and/or growth investing who wants to understand a company to the core, run the cost-benefit analysis, and evaluate all material risks *before* committing capital.

- **User zero is Lawrence himself** — the product must be genuinely used for real investment research, not just demoed.
- **Secondary audience (≈20% weighting):** technical evaluators / hiring managers in the financial-engineering space. Served by building the primary product well and documenting the engineering legibly — never by adding features the primary user doesn't need.

## D3 — Phase 1 success definition

Phase 1 has "worked" when **both** hold:

1. **Correctness:** every deterministic score (Piotroski, Altman, Beneish, Sloan) for the Phase 1 company universe matches a hand-verified or published golden dataset, enforced by regression tests.
2. **Real use:** ThesisTrace informs at least one real investment decision by user zero.

## D4 — End-state posture: portfolio-complete, startup-optional architecture

- **Governing exit criterion:** a polished, hosted, well-engineered tool that is genuinely used and can be shown. No payments, subscriptions, or growth features planned.
- **Architectural constraint:** designs must not foreclose a future B2C pivot — keep multi-user extensibility, clean auth seams, and a cost model that could scale. Do **not** build auth, multi-tenancy, or billing early; just avoid decisions that make them expensive later.

## D5 — Lens sequencing (not lens cutting)

All four lenses — **Value, Growth, Quality/Health, Integrity & Evidence** — ship in the finished product. Sequencing:

- **Phase 1:** Integrity + Quality/Health lenses (Piotroski, Altman, Beneish, Sloan — fully mechanical from XBRL), with field-level provenance.
- **Phase 2:** Value lens (DCF, reverse DCF, Graham Number, yields, multiples) and Growth lens join; first portfolio-complete release includes all four lenses.
- Rationale: the core assumption to validate first is *deterministic forensic scores computed from raw XBRL with provenance are achievable and trustworthy*. Valuation modeling is judgment-heavy and belongs after that foundation exists.

## Standing constraints carried forward from the consolidation review

- **Deterministic/LLM boundary (inviolable):** deterministic services compute every number, score, threshold, and verdict input. LLMs explain completed calculations, summarize risk-factor changes, extract qualitative signals, and answer filing Q&A — always cited, never canonical. The Fundalens LLM-generated 0–100 health score is **permanently rejected**, not deferred.
- **Stack:** Next.js/TypeScript + FastAPI/Python + Supabase Postgres (+ pgvector for first RAG). No MongoDB, Qdrant, DynamoDB, or multiple data providers before an end-to-end product exists.
  - **Exception (added 2026-07-19, via architecture spine `architecture-ThesisTrace-2026-07-19`):** Tiingo (free tier) is added in Phase 1 as a single, narrowly-scoped market-price data source — solely to supply the closing price needed for Altman Z-Score's market-value-of-equity term, which EDGAR structurally cannot provide (EDGAR gives book equity and shares outstanding, not market price). This is not the redundant multi-provider complexity the rule was written to block — Tiingo fills a gap, it doesn't duplicate a source EDGAR already covers for anything else. No other new data provider is introduced.
- **Universe:** Phase 1 = 3–5 cross-listed Canadian companies **that file US-GAAP 10-Ks on EDGAR** — **validated 2026-07-17**, see below.

## D6 — Phase 1 company universe (validated against live EDGAR data, 2026-07-17)

Checked every major cross-listed Canadian ticker against `data.sec.gov` for annual filing form, XBRL taxonomy, and history depth. Most large cross-listed Canadians (CNI, Suncor, TC Energy, BCE, Nutrien, Cameco, Thomson Reuters, CGI, Stantec, Barrick, Lightspeed, BRP) file **40-F under `ifrs-full`** and are excluded — they would break the Piotroski/Altman/Beneish/Sloan formulas as specified.

**Selected universe (4 companies, all 10-K / `us-gaap`, non-financial sector):**

| Ticker | Company | 10-K history | Note |
|---|---|---|---|
| CP | Canadian Pacific Kansas City | 11 years (since 2016) | Clean, deepest history, no caveats |
| QSR | Restaurant Brands International | 8 years (since 2019) | Clean |
| OTEX | Open Text | 24 years (since 2002) | Longest history — best base for golden-dataset regression testing |
| SHOP | Shopify | **4 fiscal years of clean US-GAAP data (FY2022–FY2025)**, not just 2 10-Ks | Included for brand recognition / demo value (serves the 20% secondary goal). Corrected 2026-07-17: comparative financials in its 10-Ks reach back to FY2022, giving 3 separate year-over-year computation periods — enough for full Piotroski/Altman/Beneish/Sloan point-in-time scoring. The real (narrower) limitation is **long historical trend charts** (a decade-plus view like OTEX's), not core score computation — and that's a Phase 2 Growth-lens concern, not a Phase 1 blocker |

**Considered and excluded:**
- **WCN (Waste Connections):** clean 10-K/us-gaap data, but re-domesticated to Delaware in 2016 — no longer meaningfully "Canadian," would undercut the differentiation narrative.
- **ENB (Enbridge):** clean 10-K/us-gaap data, optional 5th/backup if sector diversity wanted, but pipeline/infrastructure sector is capital-intensive enough that Altman Z-Score runs structurally low (calibrated on manufacturers) — would need explicit UI caveat, not a blocker.
- All IFRS 40-F filers (see above) — wrong taxonomy for the deterministic formulas as specified.

## D7 — Charting library and LLM orchestration tooling

**TradingView widgets: excluded.** A prior portfolio project (`equipulse`, at `/Users/lawrence/Documents/projects/portfolio_projects/equipulse`) already uses TradingView script-embed widgets for a public price/candlestick dashboard. TradingView widgets render off-the-shelf ticker charts, not custom visualizations over ThesisTrace's own computed data (Piotroski subscores, Altman Z components, accrual trends, provenance-tagged statement lines) — wrong fit, and would duplicate an existing portfolio piece. ThesisTrace's charts will be built directly (e.g., Recharts/visx) over its own data. If a simple price-context strip is ever wanted, it does not require the TradingView widget suite.

**LangChain: not used.** **LangGraph: adopted**, specifically for the Phase 2 filing-aware Q&A / RAG feature — not as a wrapper around Phase 1's score-explanation feature.

- **Phase 1 (score explanation):** plain, direct LLM API wrapper. Inputs are fixed, already-computed structured facts (scores + their source filing lines) — the task is narration with citations, not search. No branching or looping need, so no LangGraph here, permanently (not a stepping stone to later "upgrade").
- **Phase 2 (filing Q&A / RAG):** LangGraph, from that feature's first implementation. Justified by a genuine stateful/conditional flow: draft an answer from retrieved chunks, verify each claim is actually supported by the cited passage, re-retrieve or flag low-confidence if not (self-verifying citation loop). This ties directly to the product's Integrity-lens promise rather than being a decorative framework choice, and doubles as a deliberate learning goal for the 20% engineer-showcase weighting (D2) — motivation acknowledged and accepted as legitimate.
- **Guardrail:** LangGraph orchestration is confined to the explain/retrieve/cite/Q&A surface. It never computes or touches a canonical score — the deterministic/LLM boundary (see Standing Constraints) still holds.

## Open items before PRD

1. ~~Filing-type validation~~ — **done, see D6.**
2. Correctness golden-dataset sourcing approach.
3. Amended/restated filings (10-K/A) supersession policy.
4. Not-investment-advice disclaimer posture.
5. Monthly cost ceiling (hosting + LLM), as a number.
