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

**Status (2026-08-05).** D3.1 **closed** 2026-07-29 and was reopened and re-closed 2026-08-04 when D8
grew the universe to 7 — a claim about the universe reopens when the universe grows. D3.2 is **still
open** and has never been met, so Phase 1 has not met its own success definition, and Epics 5-9 were
planned and Epic 5 shipped on top of a half-met Phase 1. This is not a bookkeeping detail: D3.2 and
D9's binding gate are the *same* condition, so one decision packet (**D10**) closes D3.2 and unblocks
Phase 2 decomposition together. Nothing technical blocks it.

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

## D8 — IFRS / 40-F support: Canada-first (supersedes D6's blanket IFRS exclusion, 2026-07-29)

**Decision.** ThesisTrace is **Canada-first**, expanding to the US market later. That requires
supporting Canadian MJDS filers who report under IFRS on Form 40-F. D6's blanket exclusion of
IFRS filers is **narrowed, not kept**.

**Why D6 was only partly right.** D6 excluded 40-F/`ifrs-full` filers on the grounds they
"would break the Piotroski/Altman/Beneish/Sloan formulas." Verified live against
`data.sec.gov` on 2026-07-29, that reasoning does not hold in general:

| Filer | Taxonomy | Concepts tagged | Coverage | Models resolvable |
|---|---|---|---|---|
| BCE | `ifrs-full` | 288 | FY2017–2025 | 3 of 4 (no by-function SG&A) |
| Cameco | `ifrs-full` | 250 | FY2017–2025 | **4 of 4, all from directly-filed tags** |
| Suncor | `ifrs-full` | 234 | FY2017–2025 | 2 of 4 (no SG&A, no tagged retained earnings) |

IFRS filings are **not less comprehensive** — 234–288 tagged concepts is dense disclosure.

**What D6 got right, restated correctly.** Coverage varies **per filer, not per taxonomy**, and
for a reason intrinsic to IFRS *presentation* rather than tagging quality: IAS 1 permits
expenses **by nature** (raw materials, employee benefits, energy) instead of **by function**
(COGS, SG&A). A by-nature filer has no SG&A line to tag at all, so Beneish's SGAI is
unresolvable. That is the same shape as CP's missing COGS under `us-gaap`, and is handled
identically — `insufficient_data`, never a substitute or a guess.

**Consequences.**

1. Supported regimes are declared as data in `backend/canonicalization/taxonomies.py`:
   10-K/`us-gaap` and 40-F/`ifrs-full`. Adding a regime is a data change there plus its
   `MappingRule`s — scoring, the formula engine, the read API and the frontend consume
   canonical concepts and are already taxonomy-blind.
2. History is **shallower** for IFRS filers: EDGAR XBRL for 40-F filers begins ~FY2017, so
   ~9 fiscal years versus OTEX's 24 under `us-gaap`. Fine for point-in-time scoring (needs two
   consecutive years) but a real constraint on the Phase-2 Growth lens's long-trend promise.
3. Three canonical concepts must be **derived** rather than read for IFRS filers:
   `total_liabilities` (= EquityAndLiabilities − Equity), `gross_profit`
   (= Revenue − CostOfSales), and `ebit`. **`ebit` is a judgment, not arithmetic** — IFRS
   mandates no operating-profit line, so `ProfitLossBeforeTax + InterestExpense` and
   `ProfitLossBeforeTax − FinanceIncomeCost` are both defensible and give different numbers.
   That decision must live in a versioned formula spec with its rationale, visible on the
   methodology page — not buried in a mapping row.
4. **Derived facts are a weaker provenance class than filed facts**, and are currently
   indistinguishable in the API: `Provenance` exposes an accession number but not whether the
   value was selected or derived, so a computed figure wears a filed-number citation. This is
   already live for SHOP's `total_liabilities`. It must be surfaced before IFRS multiplies it
   from one concept on one filer to three on every IFRS filer.
5. Rollout order is **Cameco → BCE → Suncor** — 4/4 first, so the path is validated without a
   partial result obscuring whether a gap is a bug or reality.

**Non-goal unchanged.** The PRD's "no full market coverage" stands. This widens the addressable
Canadian universe from ~4 to a curated handful; it does not turn ThesisTrace into a screener.

## D9 — Phase 2 is sequenced around one real decision, not around the lens list (2026-08-04)

**Decision.** Phase 2 is built as a **decision workflow**, validated against a company Lawrence is
genuinely researching, rather than as parallel Value / Growth / Filing-Q&A / Thesis-Journal tracks.
This **reorders D5, it does not overturn it** — all four lenses still ship, and the Value and Growth
lenses remain Phase 2. What changes is that they are built in the order and to the depth that one
complete investment decision actually demands, instead of to their full specified breadth up front.

**Why.** Phase 1 validated a *technical* hypothesis — reliable deterministic scoring from raw filing
data is achievable — and validated it well: 7 filers, two reporting regimes, 7 of 7 hand-verified
against real EDGAR data. It did **not** validate the *product* hypothesis, that these scores,
presented this way, change or improve an investment decision. D3 encodes exactly this by requiring
both correctness **and** real use; only the first half is met. The 2026-08-02 repository-wide
direction assessment reached the same conclusion independently (§2, §3.19, §5): the current product
is closer to "a reliable forensic-score browser" than a thesis-building tool, and building Value,
Growth, Q&A, journaling and a wider universe in parallel risks "a wide but shallow research
dashboard" — five simultaneous product bets, none validated.

**Ordering.** Each increment ties to a specific research task, and the next is chosen from what the
previous one exposed:

1. **Latest-filing change detection** — what moved since last look.
2. **A narrow valuation capability** — reverse DCF with explicit assumptions, not the full Value lens.
3. **Thesis journal + thesis diff** (FR-18) — the feature most directly tied to the product's name.
4. **Growth trends** — only the depth the workflow above actually consumes.
5. **Filing Q&A** (FR-15) — last, and only once the citation-evaluation framework is ready.

**Selection criterion (binding).** After the first complete decision packet, the next feature is
chosen by *the largest observed research failure*, not by the next item on this list. If step 1
reveals that change detection was not the binding constraint, the list is re-derived — it is a
starting hypothesis, not a commitment.

**Universe posture.** Expansion follows workflow validation rather than preceding it — consistent
with PRD OQ8's resolution (manual, on demand) and counter-metric SM-C1. Breadth is not progress.

**What this does not change.** D5's four-lens end state, the deterministic/LLM boundary, D4's
portfolio-complete posture, and the D7 guardrail confining LangGraph to the explain/retrieve/cite
surface all stand unchanged.

## D10 — What a decision packet is (2026-08-05)

**Decision.** A **decision packet** is a single written record of one real investment decision in
which ThesisTrace was used. It is the unit D9's binding selection criterion operates on and the
evidence that closes D3's second condition. It is a manual artifact kept at
`_bmad-output/decision-packets/YYYY-MM-DD-<TICKER>.md`, using the template committed alongside this
decision — **not** a product feature. FR-18's thesis journal (Epic 7) may later automate part of it;
until then, automating it is out of scope and would invert the ordering D9 exists to protect.

**Why this needs a decision at all.** "Decision packet" was load-bearing in three documents —
`foundational-decisions.md` (D9's selection criterion, marked *binding*), `epics.md` (the
decomposition note for Epics 6-9) and `sprint-status.yaml` — and was defined in none of them. A gate
that is simultaneously binding and unfalsifiable has exactly two outcomes and no third: it blocks
forever because nothing clearly satisfies it, or it is waved through because nothing clearly does
not. Epics 6-9 have been undecomposed since 2026-08-04 on a criterion nobody could evaluate.

It is also the same condition as **D3.2** ("ThesisTrace informs at least one real investment decision
by user zero"), which has been open since Phase 1. D3.1 closed on 2026-07-29 with the golden dataset;
D3.2 never closed, so Phase 1 has never met its own success definition and Epic 5 shipped on top of a
half-met Phase 1. One packet closes D3.2 and unblocks D9 — they are not two pieces of work.

**A packet is complete when it records all six of these, for ONE company and ONE question:**

1. **The decision and its stake.** Written *before* opening the app. A real hold/sell/pass/size
   judgment on real money — not a rehearsal, and not "let me see what it says about X".
2. **What ThesisTrace was asked to contribute.** Which pages and which figures were actually
   consulted, not which exist.
3. **What it settled.** Each question it answered, with the figure that answered it.
4. **Where it ran out.** Each blocking gap, phrased as *a question the product could not answer*.
   Must be non-empty — see the re-derivation clause below.
5. **What was done instead.** Every place the work left ThesisTrace — raw EDGAR, a spreadsheet, a
   competitor, a napkin. This is usually where (4) is really discovered, because a gap you routed
   around is easy to forget and a tool you opened is not.
6. **The verdict.** Did it inform the decision — yes or no, plainly. This is D3.2, and a "no" is a
   valid, informative packet, not a failed one.

**The selection input.** The packet must name **one** largest research failure, not a ranked list.
D9 selects on a single item; a list defers the judgment the packet exists to force.

**Falsifiability clauses**, without which this definition would repeat the problem it fixes:

- **A packet with an empty (4) does not select anything, and is itself a finding.** If a real decision
  was reached with nothing missing, D9's roadmap is not evidence-led — it is unnecessary. Re-derive
  the list from scratch rather than defaulting to Epic 6.
- **One packet is one company and one decision.** Several shallow looks do not aggregate into one.
  The failure that matters is the one that surfaces at decision depth, and breadth is explicitly not
  progress (D9's universe posture, counter-metric SM-C1).
- **Check the named failure against the roadmap, and be suspicious of agreement.** If the largest
  failure happens to be the next list item, confirm it is genuinely the largest rather than the
  expected. D9's list is a starting hypothesis; a packet that only ever confirms it is not testing it.
- **Written during, not reconstructed after.** Item 1 before, items 2-6 during or immediately after.
  A reconstructed packet records what you now believe you needed, which is the roadmap talking back.

**What this does not change.** D9's ordering and its selection criterion stand exactly as written;
this defines the unit D9 already referred to. D3 is unchanged — this makes its second condition
measurable, not easier. D5, D4 and D7 are untouched.

## Open items before PRD

1. ~~Filing-type validation~~ — **done, see D6**, narrowed by **D8** (40-F/IFRS now supported).
2. Correctness golden-dataset sourcing approach.
3. Amended/restated filings (10-K/A) supersession policy.
4. Not-investment-advice disclaimer posture.
5. Monthly cost ceiling (hosting + LLM), as a number.
