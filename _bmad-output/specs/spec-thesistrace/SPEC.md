---
id: SPEC-thesistrace
companions:
  - ../../planning-artifacts/architecture/architecture-ThesisTrace-2026-07-19/ARCHITECTURE-SPINE.md
  - ../../planning-artifacts/prds/prd-ThesisTrace-2026-07-17/prd.md
  - ../../planning-artifacts/foundational-decisions.md
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. The architecture spine (21 ADs), the PRD (full FR detail, user journeys, glossary), and the foundational decisions (D1–D7) are adopted companions — read them alongside this kernel. Capability IDs (`CAP-n`) are stable; each cites the PRD `FR-n` it derives from so downstream epics/stories can trace both ways.

# ThesisTrace

## Why

A vision to realize — with a deliberate secondary showcase motive. Diligence-driven retail investors (user zero is Lawrence himself) want proof, not opinions, before committing capital: a company's financial health, valuation, growth durability, and earnings integrity broken into four transparent lenses, every conclusion traceable back to the actual SEC filing line item it came from. The forensic models professional analysts use — Piotroski, Altman, Beneish, Sloan — are computed **deterministically** from raw EDGAR XBRL, never guessed by an LLM; an AI layer only explains what was already computed and answers filing-grounded questions, and never originates a number or gives advice. The investor forms their own thesis; ThesisTrace makes sure that thesis is built on evidence that holds up, and keeps re-checking it as new filings arrive. Secondarily (~20% weighting), the build demonstrates real financial-engineering, deterministic-systems, AI-orchestration, and full-stack skill to technical evaluators (foundational decision D2).

## Capabilities

Phase 1 is the committed build (CAP-1…CAP-9). CAP-10…CAP-14 are directional later-phase capabilities, preserved here so the roadmap is not lost; their success criteria refine at each phase's own architecture pass.

- **CAP-1** — Company discovery & universe *(FR-1, FR-2)*
  - **intent:** Any visitor browses the Phase-1 Company Universe as cards and searches a ticker, without authentication.
  - **success:** Landing page renders CP/QSR/OTEX/SHOP cards (name, ticker, last-updated), each linking to its overview; an in-universe ticker navigates to its page; an out-of-universe ticker returns an explicit "not yet covered" — never a silent failure, generic error, or fabricated result.

- **CAP-2** — Quality/Health lens computation: Piotroski F-Score + Altman Z-Score *(FR-3, FR-4)*
  - **intent:** The system computes both scores for each company from XBRL Canonical Facts.
  - **success:** All 9 Piotroski signals and all 5 Altman ratios are individually computed and stored (not just aggregates); Altman's market value of equity = FYE Tiingo close × EDGAR shares outstanding (never a book-value substitute); financial-sector firms are excluded and capital-intensive firms carry a caveat; each formula is versioned; a missing input is `insufficient_data`, never guessed or defaulted.

- **CAP-3** — Quality/Health sub-signal display with provenance *(FR-5)*
  - **intent:** A user views each Piotroski signal (pass/fail) and each Altman component (weight) with the specific values compared.
  - **success:** Each signal shows the compared values (e.g. "ROA 2024 4.2% vs 2023 3.1% → Pass") and links to its provenance record (source filing and line item).

- **CAP-4** — Integrity lens computation: Beneish M-Score + Sloan accruals ratio *(FR-6, FR-7)*
  - **intent:** The system computes both from Canonical Facts.
  - **success:** All 8 Beneish indices are individually computed/stored; Sloan is computed via the balance-sheet approach across two consecutive balance sheets and flagged against an explicitly stated published threshold; formulas are versioned; financial-sector firms are excluded from Beneish.

- **CAP-5** — Integrity sub-signal display, provenance & data-quality flags *(FR-8)*
  - **intent:** A user views each Integrity signal's inputs and its source filing line item.
  - **success:** Same provenance-linking as CAP-3; an accounting-identity validation failure (e.g. balance sheet doesn't balance) surfaces as an explicit data-quality warning via the single `data_quality_issues` contract, never silently hidden.

- **CAP-6** — Company overview & Verdict *(FR-9, FR-10)*
  - **intent:** Each company has an overview page showing a transparent Verdict plus all currently-live lens scores, with in-page expandable sub-factor breakdowns.
  - **success:** The Verdict is a side-by-side juxtaposition of each live model's own published, cited threshold classification (Piotroski Strong 8-9 / Weak 0-1 / 2-7 Middle-mixed; Altman Safe/Grey/Distress; Beneish > −1.78; Sloan per its spec threshold) — never a blended number, never LLM-invented, band labels computed in the backend; the page states which lenses are live vs pending; individual scores stay visible and clickable; expansion is an in-page accordion linking onward to the methodology page.

- **CAP-7** — Methodology drill-down *(FR-11)*
  - **intent:** Each Deterministic Score has a dedicated methodology page.
  - **success:** The page states the formula, the exact XBRL concepts mapped to each input, the formula version in use, and links to the model's original academic source.

- **CAP-8** — AI score explanation, deterministic-first and cited *(FR-12)*
  - **intent:** A user requests a plain-language explanation of any computed score or the overall Verdict.
  - **success:** Text is rendered by a deterministic template from already-computed scores/facts; the LLM (default Claude Haiku 4.5, env-keyed, a narrow direct wrapper — no LangGraph) only polishes already-correct text and never originates a claim, number, or citation; every explanation carries inline citations to provenance records; an ungroundable statement is omitted.

- **CAP-9** — Comparison *(FR-13, FR-14)*
  - **intent:** A user adds 2–4 viewed companies to an in-session comparison and views their Verdicts and live lens scores in parallel columns.
  - **success:** The set is browser-session-only (no server persistence, no auth); minimum 2, maximum 4; the view shows exactly the lenses live in the current phase; differences beyond a stated threshold are visually highlighted.

- **CAP-10** — Cited filing Q&A *(FR-15 — Phase 2, directional)*
  - **intent:** A user asks a free-text question about a company's filings and receives a cited, evidence-checked answer or an explicit "insufficient evidence" response.
  - **success:** Every claim carries a citation to a filing passage; ungroundable claims are omitted/flagged; orchestrated via LangGraph with a real, testable self-verifying citation loop (D7).

- **CAP-11** — Value lens *(FR-16 — Phase 2, directional)*
  - **intent:** The system computes valuation metrics (DCF, reverse DCF, Graham Number, yields, multiples) with stated assumptions.
  - **success:** No valuation is shown as a bare point estimate — assumptions and a sensitivity range always accompany it; missing inputs follow the `insufficient_data` pattern.

- **CAP-12** — Growth lens *(FR-17 — Phase 2, directional)*
  - **intent:** The system computes growth-trajectory metrics across available fiscal years and presents them as historical trends via custom visualizations.
  - **success:** Trend depth honestly reflects each company's available history (the UI states the coverage window); missing periods follow the `insufficient_data` pattern.

- **CAP-13** — Thesis journal & re-verification *(FR-18 — Phase 2/3, directional)*
  - **intent:** A user saves a written thesis auto-attached to the live lens scores/facts at that moment; on return the system produces a Thesis Diff against current values.
  - **success:** Persisted browser-locally (no auth); the diff is presented per-claim/per-metric, not as a single "something changed" flag.

- **CAP-14** — Notifications & deep-research requests *(FR-19, FR-20, FR-21 — Phase 3, directional)*
  - **intent:** Email-only (no account) notifications for thesis re-verification availability and deep-research fulfillment.
  - **success:** A thesis-diff email fires once per new filing per thesis with a summary of what changed; a deep-research request is queued with a stated SLA and answered with citations (or an explicit insufficient-evidence notice) via a real transactional email provider.

## Constraints

- **Deterministic/LLM boundary — inviolable (D5, D7).** Deterministic services compute every number, score, threshold, and verdict input. The LLM only explains, summarizes, and answers — always cited, never canonical. An LLM-originated health score is permanently rejected, not deferred.
- **The 21 architecture ADs are binding** (adopted `ARCHITECTURE-SPINE.md`): batch-pipeline-write / read-only-query CQRS split (AD-1), immutable raw store + versioned canonicalization (AD-2/AD-3), versioned formula specs applied by one shared decimal/rounding engine (AD-5/AD-15), append-only `score_runs` with latest-non-superseded = current (AD-6), tri-state signal status never coerced to a defaulted zero (AD-16), single `data_quality_issues` contract/owner (AD-17), canonical `score_results` shape + `signal_key` vocabulary (AD-18), provenance as a first-class invariant (AD-19), sector-scope applicability state (AD-20).
- **Data sources (D7 exception).** SEC EDGAR Company Facts API is primary, Inline XBRL is the audit/fallback; Tiingo free tier is the **only** additional provider, solely for Altman's FYE closing price. No other provider in Phase 1. EDGAR access is disciplined: identifying User-Agent, ≤10 req/s, cached, retried, idempotent, replayable (AD-9).
- **Phase-1 Company Universe is fixed and US-GAAP-only (D6):** CP, QSR, OTEX, SHOP — all 10-K / `us-gaap`, non-financial. IFRS / 40-F filers are excluded from the current formula set.
- **No end-user auth in Phase 1 (D4).** Public, read-only. Admin/recompute is operator-only behind a shared-secret header (AD-10). Designs keep clean auth seams for a possible future B2C pivot but build no auth, multi-tenancy, or billing early.
- **Cost ceiling ~$25/month total** (hosting + data + LLM). Fixed cost ~$8–10/mo: Render web + cron (AD-13) + Supabase free Postgres 17 + Tiingo free + Vercel free. The daily batch ingestion job doubles as the Supabase keep-alive ping.
- **Phase-1 LLM is a plain, direct API wrapper — no LangChain/LangGraph (D7).** Default Anthropic Claude Haiku 4.5, key via env var, provider swappable, out of the numeric loop (AD-21). LangGraph is reserved for the Phase-2 filing-Q&A self-verifying citation loop only.
- **Visualizations are custom-built** (e.g. Recharts/visx) over ThesisTrace's own computed data — no off-the-shelf charting widgets (TradingView explicitly excluded, D7).
- **Web-only, responsive; no native mobile app.** Stack pinned: Next.js 16.2.x / React 19.2.x on Vercel; FastAPI 0.139.x + Pydantic 2.13.x + SQLAlchemy 2.0.51 (async) / Python 3.12–3.13 on Render; Postgres 17 (Supabase).
- **SM-1 correctness is the Phase-1 quality bar.** A golden-dataset regression harness (all four models' outputs vs hand-verified/published values) is in Phase-1 scope; only its CI automation is Phase-4-deferred.

## Non-goals

- **Never investment advice** — the system presents evidence and lets the investor form their own thesis. Permanent.
- **No LLM-generated canonical scores, ever** — every number/score/threshold is deterministic.
- **No brokerage integration, trade execution, or broker/fee comparison** in any phase.
- **No full market coverage** — not the S&P 500, not broad TSX/TSXV; the universe stays deliberately narrow and honestly labeled.
- **No user accounts or passwords** beyond the minimal Phase-3 email-only capture for notifications.
- **No off-the-shelf charting widgets** (e.g. TradingView).
- **No IFRS-reporting companies** in the current Piotroski/Altman/Beneish/Sloan formula set.
- **No native mobile app** — web-only (responsive).
- **No broad news/sentiment aggregation via paid data providers.**
- **No sector heatmap, no draggable/resizable dashboard UI.**
- **No formal WCAG accessibility target for v1.**
- **No formal performance, uptime, or security NFR targets for v1** — correctness (SM-1) is the quality bar; operational rigor is Phase-4 work.
- **No SEDAR+ / TSX-only (non-EDGAR) Canadian companies.**

## Success signal

- **SM-1 (correctness):** 100% of Piotroski, Altman, Beneish, and Sloan scores computed for CP/QSR/OTEX/SHOP match a hand-verified or published golden dataset, enforced by regression tests.
- **SM-2 (real use):** ThesisTrace informs at least one real investment decision by user zero within 3 months of Phase-1 launch.
- *(Secondary: SM-3 a technical reviewer engages with the methodology/Q&A and it holds up; SM-4 the primary user returns to Comparison or the Thesis Journal unprompted. Counter-metrics: SM-C1 do not grow universe breadth before correctness is solid; SM-C2 do not optimize notification volume or open rate.)*

## Open Questions

- **Golden-dataset sourcing (Phase 1, blocks SM-1):** where do the hand-verified/published Piotroski/Altman/Beneish/Sloan values for CP/QSR/OTEX/SHOP come from, and how is the dataset kept current as new filings arrive?
- **Not-investment-advice disclaimer (Phase 1):** exact wording, placement (every page? footer? first-visit notice?), and whether a Canada-specific legal review is warranted.
- **Later-phase (tracked, not blocking Phase 1):** deep-research SLA design (FR-19), thesis browser-local persistence resilience (FR-18), email retention/deletion policy (FR-19–21), the Phase-2 universe-expansion process, and lens sub-metric depth beyond the four named models.
