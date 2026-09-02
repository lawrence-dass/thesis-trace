# Phase 2 Feature-Hypothesis Catalog

**Status: a catalog of hypotheses, not a roadmap.** Written 2026-09-02 from a two-session
brainstorm on what a comprehensive, fully deterministic single-stock diligence platform would
need beyond what ships today. Nothing here is committed, sequenced, or decided.

**What governs selection from this list:** D9 (the next feature is chosen by *the largest observed
research failure*, named in a decision packet) and D10 (what a packet is). Two packets exist —
`decision-packets/2026-09-01-CPB.md` and `2026-09-01-ZTS.md` — with section 1 written and sections
2–6 pending. Until a packet's "largest research failure" is filled in, this catalog selects nothing.
Its purpose is narrower: when a packet names a gap, the answer should already be here with its
inputs, coverage and cost worked out, so the spike starts from a hypothesis rather than a blank page.

**How to read it.** Every item is keyed to the three questions both packets ask in section 1,
because those are the only questions with evidence behind them:

- **Q1** — Is management allocating capital well enough to trust the growth?
- **Q2** — Is the balance sheet actually as clean as it looks?
- **Q3** — Is the price already too rich relative to intrinsic value?

An item that serves none of the three is listed under "Considered and parked", not in the
main tables. Field meanings:

| Field | Meaning |
|---|---|
| **Inputs** | The XBRL concepts or EDGAR metadata the deterministic computation reads. Tag names are *candidates* — none has been live-verified for per-year coverage. |
| **Coverage** | How many of the 9 current filers the data source can structurally reach. `9/9` = both regimes. `6/9` = 10-K filers only (CP, QSR, OTEX, SHOP, CPB, ZTS); the three 40-F filers (CCJ, BCE, SU) are foreign private issuers and are exempt from the filing type. |
| **Bites** | Which current filer the item is most likely to change a reading on. Chosen by code path, not convenience (DoD rule 5). |
| **Overlap** | Whether any shipped model already computes a version of this — checked because OQ9's proposed metrics silently duplicated DSRI and the Sloan accrual (2026-08-04 learning). |
| **Cost** | Rough sessions to ship *to the live-data DoD*: per-year live verification across the relevant regimes, mapping-spec `note`, golden-fixture rebuild (fixtures are trimmed subsets and are blind to every new concept — Epic 6 learning), browser check. "Deterministic" is not "free". |
| **Verified** | Always `no` at catalog time. Flip only with an `engineering-findings.yaml` entry. |

---

## Design framing — still open, not decided

**This section is the thesis the catalog below serves, not part of the catalog itself.** The
tables are a flat hypothesis list; this is the shape Lawrence wants to re-think before any of it
becomes a decision packet's answer. Written from the first brainstorm session (before the second
session's item-by-item critical pass that produced the tables below) — captured here now because
it existed only in conversation transcripts, in neither this file nor `CURRENT.md`, and a fresh
session had no way to recover it except asking Lawrence to re-paste his own messages.

**The thesis, as landed on (not locked):** Value and Growth — D5's two Phase-2 lenses — are not
two independent models. They **share one deterministic foundation** and differ only in which
question is asked of it: Value asks "is the price already too rich for what this foundation
implies", Growth asks "is the implied trajectory durable". They should render as **separate
cards, never blended into one score** — the same principle D12 already applies across all four
Phase-1 models (no filled polygon, no aggregate number). Whether that shared foundation is the
reverse-DCF machinery already shipped in Epic 6, the incremental-ROIC identity below, or both, is
exactly the open question.

**Two prerequisites were identified as missing before either lens can be built on that
foundation — framed as GATES, not as catalog items to schedule:**

1. **A disclosed cost-of-capital / hurdle-rate figure.** The reverse DCF currently takes its
   discount rate as an external assumption; Value needs a defensible way to say what rate the
   business itself is being judged against. Operationalized as catalog item **Q3.2**, and its row
   already records the real difficulty: this is likely a text-extraction problem (an
   impairment-testing note), not an XBRL tag, so it may belong with Epic 9's citation framework
   rather than shipping standalone.
2. **Mauboussin's incremental-ROIC identity** — `growth = reinvestment rate × return on
   incremental capital`. This is the candidate for the "shared foundation" itself: it turns
   reported growth into growth that was *paid for*, which is what makes it useful to both lenses
   at once rather than to Growth alone. Operationalized as catalog item **Q1.2**.

**What would resolve this framing into a decision:** either a decision packet's "largest research
failure" lands on Q1.2 or Q3.2 specifically (D9's selection criterion, operating as designed), or
Lawrence revisits the thesis directly and it becomes a D5 amendment naming Value/Growth's actual
relationship, at which point this section should be deleted and the decision recorded in
`foundational-decisions.md` instead of here.

---

## Correction carried from the brainstorm: proxy and insider data are 6/9, not universe-wide

The brainstorm's two top picks — executive-compensation alignment (DEF 14A) and insider
transactions (Form 4) — were rated "close to free structured data". That is true only for the
10-K filers. **Foreign private issuers are exempt from the US proxy rules (Reg 14A) and from
Section 16.** BCE, Suncor and Cameco file a Canadian management information circular as a 6-K
exhibit (unstructured), and file no Form 4s. The Inline-XBRL-tagged Pay-versus-Performance table
(Reg S-K Item 402(v)) is likewise a domestic-registrant requirement.

Consequences: both items are `6/9` coverage, and under AD-16 the three IFRS filers would render
`insufficient_data` for them — correct, but a third of the universe blank on a headline card.
Under D11 the next filers are expected to be 10-K, so the gap does not grow; it also does not
close. **Verify before locking:** which of the six 10-K filers actually tag Item 402(v) (mandatory
since FY2022 for large accelerated filers — confirm per filer, not per rule).

---

## Q1 — Capital allocation: can the growth be trusted?

*Both packets lead with this. CPB's version is concrete — Sovos Brands / Rao's, the soup-to-snacks
shift — which makes acquisition accounting the sharpest sub-question.*

| # | Item | Inputs (candidate tags) | Coverage | Bites | Overlap | Cost | Verified |
|---|---|---|---|---|---|---|---|
| Q1.1 | **Goodwill share of assets + impairment history** — the deterministic proxy for "did the acquisition work". Rising goodwill followed by `GoodwillImpairmentLoss` is the signature of value-destructive M&A. | `Goodwill`, `Assets`, `GoodwillImpairmentLoss`; IFRS `Goodwill`, `ImpairmentLossRecognisedInProfitOrLossGoodwill` | 9/9 | **CPB** (Sovos), OTEX (serial acquirer), QSR | None shipped | 1–2 | no |
| Q1.2 | **Incremental ROIC / reinvestment identity** — Mauboussin: `growth = reinvestment rate × return on incremental capital`. Turns "growth" into "growth that was paid for at what return". | NOPAT (EBIT × (1 − ETR)), invested capital deltas, capex, D&A, working-capital change | 9/9 | **ZTS** (premium-growth thesis), SHOP | None shipped. Reverse DCF (Epic 6) *implies* growth; this measures *achieved* incremental return. Distinct. | 2–3 (needs a spec, `invested_capital` derivation, cyclical companion — see Q1.7) | no |
| Q1.3 | **Buyback price discipline** — average repurchase price vs. the period's valuation range. Closes the loop on the original allocation-buckets table. | `PaymentsForRepurchaseOfCommonStock` ÷ `StockRepurchasedDuringPeriodShares` (or `TreasuryStockSharesAcquired`); IFRS `PaymentsToAcquireOrRedeemEntitysShares` + share count; Tiingo close for the range | 9/9 for dollars; **share count unverified per regime** | QSR, CP, OTEX | None shipped | 1–2, but see Q1.4 — ship together | no |
| Q1.4 | **SBC-adjusted FCF + net dilution** — a buyback that only offsets stock-based-comp issuance returns nothing. Net share-count trajectory is the honest number. | `ShareBasedCompensation`, diluted WASO YoY, `StockIssuedDuringPeriodSharesShareBasedCompensation`; IFRS `ExpenseFromSharebasedPaymentTransactions` | 9/9 | **SHOP** (SBC-heavy), ZTS | Sloan reads accruals, not SBC. Distinct. | 1 | no |
| Q1.5 | **Executive-compensation alignment** (DEF 14A / Item 402(v) PvP). Munger's "show me the incentive": a bonus tied to revenue with no ROIC/capital-efficiency term is a *leading* red flag for Q1, where Q1.1–Q1.4 are lagging. | Item 402(v) Inline-XBRL: `PeoTotalCompAmt`, `PeoActuallyPaidCompAmt`, company-selected measure; metric list is text | **6/9** | CPB, ZTS, SHOP | None shipped. New EDGAR filing type — ingestion is new infrastructure, not a mapping row. | 3+ (new form type, new parser, plus the metric *names* need an LLM or a manual table) | no |
| Q1.6 | **Capex vs. D&A** (maintenance starvation). Several years of capex < D&A inflates FCF now and is paid for later; a reverse DCF on starved FCF flatters the stock. | capex (mapped, Epic 6), `DepreciationDepletionAndAmortization`; IFRS `DepreciationAndAmortisationExpense` | **8/9** — SU has no capex tag filed at all, permanently `insufficient_data` for this signal; OTEX FY2008-2019 only (D&A tag gap after FY2019 — its live capex sign defect FY2007-2009 was found and fixed the same day, `otex_capex_sign_error_fy2007_fy2009`, concepts_v11) | **CP** (clean, FY2008-2025); OTEX FY2008-2019 only — SU, half the original rationale, cannot compute this signal at all | Epic 6 already stores capex. Cheapest item in the catalog. | ≤1 | **yes (2026-09-02)** |
| Q1.7 | **Cyclical normalization** — mid-cycle / multi-year-average ROIC and margins as a companion to single-year figures. A strong Piotroski at peak earnings is the classic value trap. | Existing mapped inputs over a 5–10y window | 9/9 (window length limited: 40-F XBRL starts ~FY2017 — D8 learning) | **CP, SU, CCJ** | Trajectory (Epic 5) shows direction per model; this normalizes *level*. Distinct. | 1–2 as a presentation of existing data; foundational to Q1.2 and Q3.1 | no |

## Q2 — Is the balance sheet as clean as it looks?

*"As it looks" is doing the work. Altman and the debt cards read reported liabilities; the items
here are the liabilities and events that do not present as debt.*

| # | Item | Inputs (candidate tags) | Coverage | Bites | Overlap | Cost | Verified |
|---|---|---|---|---|---|---|---|
| Q2.1 | **Defined-benefit pension deficit** — debt that does not look like debt. | `DefinedBenefitPlanFundedStatusOfPlan` (or plan assets − PBO); IFRS `NetDefinedBenefitLiabilityAsset` | 9/9 | **CP, BCE** (large DB plans), CPB | Not in Altman's X-terms; near-term debt cards exclude it. Distinct. | 1–2 | no |
| Q2.2 | **Lease liabilities + contingencies as a "hidden liabilities" card** with Q2.1 | `OperatingLeaseLiability`, `FinanceLeaseLiability`, `LossContingencyAccrualAtCarryingValue`; IFRS `LeaseLiabilities` | 9/9 | QSR (franchise real estate), BCE | Post-ASC 842 / IFRS 16 leases are on-balance-sheet, so this is mostly *surfacing*, not deriving. | 1 (bundle with Q2.1) | no |
| Q2.3 | **Dividend coverage by FCF, after buybacks** — `dividends ÷ (CFO − capex)`. | `PaymentsOfDividends`, CFO, capex (both mapped); IFRS `DividendsPaidClassifiedAsFinancingActivities` | 9/9 | **BCE** (paid above FCF for years, cut in 2025), CPB (high payout) | None shipped | ≤1 | no |
| Q2.4 | **Payables stretching / cash-conversion cycle** — DPO and DIO. A CFO uptick from delaying suppliers is the "cash flow looks fine" move Beneish does not catch. | `AccountsPayableCurrent`, `InventoryNet`, COGS; IFRS `TradeAndOtherCurrentPayables`, `Inventories` | 9/9 where COGS exists — **CP has no COGS tag** (railroad functional expenses) → `insufficient_data` for DIO/DPO on CP; same shape for by-nature IFRS filers | CPB, ZTS, SHOP | **Partial: DSO is already Beneish's DSRI.** Add DPO and DIO only; never re-compute DSO under a second name. | 1 | no |
| Q2.5 | **Forensic filing events from EDGAR form metadata** — no XBRL parsing: count of 10-K/A restatements, NT 10-K late filings, 8-K Item 4.01 auditor changes, 8-K Item 4.02 non-reliance. | `submissions.json` form-type index per CIK | 9/9 (40-F/A, 6-K analogues need their own mapping) | All — a universe-wide card | None shipped. **Directly adjacent to `canonical_facts_amendment_gap`**: today a 10-K/A's restated figures never reach `canonical_facts`; this item would at least *count* them. Fix the gap first. | 1–2 | no |
| Q2.6 | **Effective tax rate vs. statutory** — rising earnings with a falling ETR is a flag Beneish's eight indices do not include. | `IncomeTaxExpenseBenefit` ÷ `IncomeLossFromContinuingOperationsBeforeIncomeTaxes…` (note: the two us-gaap pre-tax tags differ on equity-method income — Epic 6 learning) | 9/9 | OTEX, SHOP | None shipped | 1 | no |
| Q2.7 | **"Non-recurring" charges that recur** — `RestructuringCharges` present in ≥3 of the last 5 years. | `RestructuringCharges`; IFRS `RestructuringProvision`-related | 9/9 | **CPB**, OTEX | None shipped | ≤1 | no |
| Q2.8 | **Ownership / skin in the game** — trailing-12-month net insider buying (Form 4, structured XML) and 13D/13G activist stakes. | Form 4 XML (`nonDerivativeTransaction`), Schedule 13D/G index | **6/9** for Form 4; 9/9 for 13D/G | CPB, ZTS | None shipped. New form type. | 2–3 (new ingestion) | no |

## Q3 — Is the price too rich relative to intrinsic value?

*Epic 6 already computes the implied growth. What is missing is the means to judge it — ZTS's
section 1 asks exactly this: "is today's price asking for more than the business has ever
actually delivered?"*

| # | Item | Inputs | Coverage | Bites | Overlap | Cost | Verified |
|---|---|---|---|---|---|---|---|
| Q3.1 | **Base-rate comparison for the reverse-DCF implied growth** — Mauboussin & Callahan, *The Base Rate Book* (Credit Suisse, 2016): historical distributions of 10-year sales / earnings growth by starting size. Renders "the price implies X% for N years; Y% of companies this size have ever done that". | Reverse-DCF output (stored, Epic 6) + a versioned reference table transcribed from the primary source | 9/9 | **ZTS** (the packet's own question), SHOP | Extends Epic 6; does not re-solve anything. **The reference table is data ThesisTrace publishes under its own name — cite the source and version it like a formula spec.** | 1–2, of which most is transcribing and citing the table correctly | no |
| Q3.2 | **Disclosed cost-of-capital / hurdle rate** — the discount-rate input the reverse DCF currently takes as an assumption. Some filers disclose a WACC or hurdle in impairment-testing notes. | 10-K goodwill-impairment note (text); IFRS `DiscountRateUsedToReflectTimeValueOfMoneyRegulatoryDeferralAccountBalances` is *not* it — needs checking | Unknown — **text extraction**, belongs with Epic 9's citation framework unless a tag is found | ZTS, CPB | Reverse DCF sensitivity (35 solves) already spans the rate; this would anchor one column. | Unknown until the disclosure form is checked per filer | no |
| Q3.3 | **Achieved-vs-implied growth** — the historical growth ThesisTrace already can compute against the growth the price implies. The one-line version of Q3.1 that needs no external table. | Revenue CAGR (`historical_revenue_cagr`, **shipped**) vs. reverse-DCF implied rate (`implied_growth`, **shipped**). FCF CAGR is **not shipped** — no historical FCF series exists anywhere; only the single latest year's FCF is stored | **8/9** — SU has no capex tag at all (same root cause as Q1.6), so `implied_growth` never resolves; its revenue CAGR alone does, but the comparison needs both halves | ZTS (was frozen at FY2017 data until `zts_stale_reverse_dcf_cash_gap` fixed it same day), SHOP | Uses shipped data for the revenue-CAGR half only. **Comparing revenue CAGR against a FCF-implied rate is apples-to-oranges** — the reverse DCF solves for an FCF growth rate, not a revenue growth rate, so a margin-expanding or SBC-heavy filer (SHOP) can show a real divergence that is a definitional mismatch, not a genuine achieved-vs-implied gap. An FCF CAGR (mirroring `historical_revenue_cagr`'s existing pattern, substituting FCF) is the apples-to-apples comparison and is the part that needs new code. Distinct from Trajectory (per-model score direction). | 1 (not ≤1 — half the claimed "shipped data" isn't) | **yes (2026-09-02)** |
| Q3.4 | **Graham Number, earnings / FCF yields, EV multiples** — D5's original Value-lens list. | Mapped inputs + Tiingo close | 9/9 | All | Named in D5 already; listed for completeness, not newly proposed. | 1–2 | no |

## Cross-cutting — serves all three, or D9 step 1 (change detection)

| # | Item | Inputs | Coverage | Bites | Overlap | Cost | Verified |
|---|---|---|---|---|---|---|---|
| X.1 | **Textual change in the 10-K itself** — Cohen, Malloy & Nguyen, "Lazy Prices", *Journal of Finance* 75(3), 2020: year-over-year similarity of Risk Factors and MD&A predicts returns; the filers that *change* their language are the ones to read. Cosine similarity on text — deterministic, no LLM. | 10-K / 40-F full-text sections (needs section extraction, not XBRL) | 9/9 | All | This *is* D9 step 1 ("what moved since last look") with a citation behind it. Epic 5 covers numeric movement only. | 2–3 (full-text ingestion is new; the similarity itself is trivial) | no |
| X.2 | **Segment revenue and margin** (dimensional XBRL) + **customer concentration** (`ConcentrationRiskPercentage1` with customer axis). | `us-gaap` dimensional facts on `StatementBusinessSegmentsAxis` | 9/9 in principle; dimensional parsing is new — company-facts JSON is *non-dimensional*, so this needs the full XBRL instance, not the current feed | CPB (soup vs snacks), ZTS (US vs international) | None shipped. **Infrastructure change**, not a mapping row. | 3+ | no |

---

## Explicit non-goals (confirmed in the brainstorm — record so they do not drift in)

- **Position sizing / portfolio construction.** Kelly, diversification, correlation are a different
  discipline, require accounts and position tracking, and conflict with the Phase 1 "no accounts"
  decision (D4). Everything above is single-stock analysis. Epic 7 (thesis journal) must not
  become a portfolio tracker by accretion.
- **Any blended score across items.** Every item renders as its own card with its own tri-state
  status (AD-16); nothing aggregates them (D12's visual-blend prohibition, the Verdict rule).
- **Short interest, CDS spreads, bond yields, consensus estimates.** Each needs a new paid or
  non-EDGAR provider, which the standing "no multiple providers" constraint blocks. Not a gap
  in the catalog — a boundary.
- **Fair-value opinions and moat ratings.** Excluded by the deterministic/no-advice boundary
  (D11 point 3). Q3.1 gives the reader a base rate; it does not say "overvalued".

## Considered and parked (LLM-side, or text-only — belong with Epic 9, not here)

- Material weakness in ICFR (10-K Item 9A) — text.
- Related-party transactions — text, note-level.
- Critical audit matters — auditor's report, text.
- Risk-factor summarization — already the LLM's job under the standing constraints; X.1 gives it a
  deterministic trigger.
- A fifth named lens. The brainstorm's "cash-flow alignment" pillar is **capital allocation**, which
  D5's four lenses (Value, Growth, Quality/Health, Integrity) do not name. Whether it becomes a
  lens or stays Q1's sub-metrics is a D5 amendment — a decision, not a catalog entry.

---

## How this catalog is consumed

1. A decision packet fills in sections 2–6 and names **one** largest research failure.
2. Grep this file for the failure. If it is here, the row's inputs, coverage and overlap notes
   seed a spike; if it is not, the catalog was wrong about the hypothesis space — add the row
   *after* the spike, never before.
3. The spike runs to the live-data DoD (`CLAUDE.md`): per-year coverage on live `data.sec.gov`
   for every filer the item reaches, mapping-spec `note`, golden-fixture check, browser render.
   Ask for every domain and CIK in one request.
4. Record the result in `engineering-findings.yaml`; flip `Verified` here with the finding key.
5. Only then decompose stories. D9's ordering list (change detection → reverse DCF → thesis
   journal → growth → Q&A) is a hypothesis; the packet's named failure outranks it.

**What would make this document wrong:** a packet whose section 4 is empty. Under D10 that is a
finding — the roadmap is not evidence-led — and the right response is to re-derive from scratch,
not to pick the cheapest row here.
