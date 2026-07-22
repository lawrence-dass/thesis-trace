---
title: ThesisTrace
status: final
created: 2026-07-17
updated: 2026-07-21
---

# PRD: ThesisTrace

## 0. Document Purpose

This PRD is for Lawrence (sole PM, engineer, and primary user of the finished product) and for any future technical reviewer assessing the engineering behind it. It builds on the locked foundational decisions in `foundational-decisions.md` (product name, primary user, success definition, end-state posture, lens sequencing, validated Phase 1 company universe, and technology exclusions/inclusions) and on the original LedgerLens/Fundalens consolidation review — this document does not restate those; it references and extends them. Requirements are grouped by feature, with globally-numbered, stable Functional Requirement (FR) IDs so downstream architecture, UX, and epic/story work can cite them directly.

## 1. Vision

ThesisTrace is an evidence-backed equity intelligence platform for retail investors who want proof, not opinions, before they commit capital. Rather than trusting a single opaque score or a stranger's hot take, an investor sees a company's financial health, valuation, growth durability, and earnings integrity broken into four distinct, transparent lenses — every conclusion traceable back to the actual filing line item it came from.

It starts narrow and honest: a small set of cross-listed Canadian companies with clean, verifiable US-GAAP data, computed with the same deterministic forensic models professional analysts use (Piotroski, Altman, Beneish, Sloan) — not an LLM guessing at a number. An AI layer explains what's already been computed and answers filing-grounded questions, but it never originates a score or tells the investor what to do. The investor forms their own thesis; ThesisTrace's job is to make sure that thesis is built on evidence that actually holds up — and, uniquely, to keep checking that evidence against reality as new filings arrive.

## 2. Target User

### 2.1 Jobs To Be Done

- **Functional:** When I'm considering a Canadian-relevant equity, I want to see whether its financials actually hold up, so I can tell a genuine opportunity from a value trap.
- **Functional:** When I've found a company that looks cheap or fast-growing, I want to check its earnings quality before I trust the headline numbers.
- **Functional:** When I've researched two or more candidates, I want to compare them side by side so I can decide between them with evidence, not memory.
- **Emotional:** I want confidence that I'm reasoning from evidence, not being sold a narrative — including my own optimism.
- **Identity/social:** I want to back companies genuinely worth owning because they're Canadian-connected and strong — not just because they're familiar.
- **Contextual (secondary, ~20% weighting):** As the builder, I want this to visibly demonstrate real skill — financial modeling, deterministic engineering, AI orchestration, full-stack, cloud — to technical evaluators in the financial-engineering space.

### 2.2 Non-Users (v1)

- Day traders / technical (chart-pattern) analysts — no candlestick tools, no technical indicators, no TradingView-style widgets (see `foundational-decisions.md` D7).
- Investors wanting full market coverage (S&P 500, broad TSX/TSXV) — only 4 companies in v1.
- Anyone wanting portfolio management, trade execution, or brokerage/fee comparison — explicitly out of v1 (see Non-Goals).
- Institutional or compliance users needing audit-grade formal reports — this is a personal research tool, not a compliance product.

### 2.3 Key User Journeys

- **UJ-1. Daniel checks whether a Canadian industrial name's numbers actually hold up.**
  - **Persona + context:** Daniel, a Canada-first retail investor who wants to back companies genuinely worth owning — not just familiar names. He's screening for his next position.
  - **Entry state:** Unauthenticated, first visit, landing page directly (no login anywhere in v1).
  - **Path:** Lands on the homepage, sees the Phase 1 starter list (CP, QSR, OTEX, SHOP) as explorable cards — no quiz, no gate. Clicks into Canadian Pacific Kansas City. Sees a company overview: a nutshell verdict up top, with expandable sub-factor breakdowns underneath (Piotroski, Altman, Beneish, Sloan — each showing its pass/fail signals). Expands the Integrity lens specifically — sees why a signal failed or passed, each tied to the actual line item in CP's real EDGAR filing.
  - **Climax:** He can see, in plain terms backed by real filing citations, whether CP's reported numbers are trustworthy and financially healthy — not an opaque score he has to just believe.
  - **Resolution:** Confident either way, he closes the tab or clicks into a second company (QSR) to compare. No push toward a brokerage — that's out of v1 entirely.
  - **Edge case:** He searches a ticker outside the Phase 1 universe — the app says plainly "not yet covered" rather than erroring or faking a result.

- **UJ-2. Daniel, in skeptical mode, goes under the hood.**
  - **Persona + context:** Daniel, before trusting any verdict with real money, wants to see the actual methodology — not just accept the number. (This same journey doubles as the path a technical evaluator from the secondary audience walks when assessing the engineering; the surface is identical, only the motivation differs.)
  - **Entry state:** Already on a company page (continues from UJ-1's climax).
  - **Path:** Clicks through from an expandable sub-factor into a dedicated methodology page for that score (e.g., "how Beneish M-Score is calculated here"). Sees the actual formula, the specific XBRL fields it pulled, and any provenance/confidence notes if data was incomplete. Optionally asks the AI Q&A layer a direct question ("why did the M-Score flag this?") and gets a cited answer grounded in the filing.
  - **Climax:** Full trust established — or a specific, well-founded doubt — because nothing is hidden behind a black-box number.
  - **Resolution:** Returns to the main verdict view with either confirmed trust or a specific, articulable concern.

- **UJ-3. Daniel decides between two candidates he's already vetted.**
  - **Persona + context:** Daniel, having independently reviewed CP and QSR (each via UJ-1's flow), can't tell from memory alone which is the stronger pick.
  - **Entry state:** Unauthenticated, has just come from viewing QSR's company page, CP viewed earlier in the session.
  - **Path:** From QSR's page, adds it to an in-session comparison. Navigates to CP, adds it too. Opens a side-by-side comparison view: both companies' verdicts and lens scores shown in parallel columns.
  - **Climax:** Sees at a glance where they diverge — e.g., CP's Integrity score is cleaner, QSR's is close but with one flagged accrual signal — evidence-backed, not just two numbers.
  - **Resolution:** Picks a direction with a specific, articulable reason, or decides to dig deeper into the one flagged signal before deciding.

- **UJ-4. Daniel's thesis gets tested by reality.**
  - **Persona + context:** Daniel decided CP was a strong pick (from UJ-1/UJ-3) and wants to record why, not just remember a vague impression.
  - **Entry state:** On CP's overview page, sometime after forming a view.
  - **Path:** Writes a short thesis; the app auto-attaches the specific lens scores/facts live at that moment (e.g., "Piotroski 8/9, Beneish M-Score -2.1, no accrual red flags"). Weeks later, a new 10-Q lands; Daniel returns and sees a direct diff: which of his own cited reasons still hold, which changed, and by how much.
  - **Climax:** He's not relying on memory or vibes — he sees precisely whether the evidence that convinced him originally still stands.
  - **Resolution:** Thesis confirmed (confidence reinforced) or specifically undermined (he knows exactly what changed and can act on that, not on a vague feeling something's off).

- **UJ-5. Daniel gets notified instead of having to remember to check back.**
  - **Persona + context:** Daniel has a saved Thesis on CP (from UJ-4) and, separately, a nagging question about QSR's recent guidance he wants explored in depth.
  - **Entry state:** On CP's or QSR's overview page.
  - **Path:** For CP, no action beyond the already-saved Thesis is needed — the system watches for new filings automatically. For QSR, he submits a Deep Research Request with his open-ended question and an email address; no account is created.
  - **Climax:** Days later, two emails arrive independently: one is CP's Thesis Diff ("here's what changed since your thesis"), the other is the completed deep research on QSR delivered as a cited write-up.
  - **Resolution:** Daniel opens each from his inbox, reads the evidence-grounded update, and decides whether to revisit either company in the app.
  - **Edge case:** If a Deep Research Request can't be answered with sufficient evidence within the SLA, the notification says so explicitly rather than presenting a shaky answer as if it were solid.

## 3. Glossary

- **Company Universe** — The fixed set of companies ThesisTrace covers in a given phase. Phase 1: CP, QSR, OTEX, SHOP.
- **Lens** — One of four independent analytical perspectives on a company: Value, Growth, Quality/Health, Integrity & Evidence. Each lens produces its own scores; none are hidden inside a single opaque number.
- **Verdict** — The company-level synthesis a user sees first, built transparently from the underlying lens scores — never a number the LLM invents.
- **Deterministic Score** — A financial metric computed by a fixed, versioned formula from Canonical Facts (e.g., Piotroski F-Score, Altman Z-Score, Beneish M-Score, Sloan accruals ratio). Never generated by an LLM.
- **Canonical Fact** — A single normalized financial data point (e.g., "Total Assets, FY2024") extracted from a filing, tied to Provenance.
- **Provenance** — The traceable link from a Canonical Fact or Deterministic Score back to the specific filing and line item it came from.
- **Citation** — A user-facing reference (in AI explanations or Q&A answers) pointing to the specific filing passage supporting a claim.
- **Filing** — A structured SEC EDGAR submission (10-K or 10-Q) containing XBRL-tagged financial data.
- **Explanation** — LLM-generated narrative describing an already-computed Deterministic Score or Verdict. Never originates a number.
- **Filing Q&A** — The LLM-driven, citation-grounded question-answering feature over a company's filings (Phase 2).
- **Comparison** — A user-initiated, side-by-side view of two or more companies' Verdicts and lens scores (UJ-3).
- **Methodology Page** — A dedicated page per Deterministic Score explaining its formula and the exact fields used, satisfying UJ-2's drill-down.
- **Thesis** — A user's own written investment rationale for a company, auto-attached to the live lens scores/facts at the time of writing (UJ-4).
- **Thesis Diff** — The system's later comparison of a saved Thesis's cited facts against current values, surfacing what changed.
- **Deep Research Request** — A user-submitted, open-ended research question about a company, queued for asynchronous, more thorough agent-driven investigation than instant Filing Q&A, delivered via Notification when complete.
- **Notification** — An email sent to a user-provided address when a Thesis Diff becomes available or a Deep Research Request is fulfilled. Requires only an email address, never a full account.

## 4. Features

### 4.1 Company Discovery & Universe
**Description:** The entry point to the product — a starter list of the current Company Universe plus ticker search, with honest handling of companies not yet covered. Realizes UJ-1.

#### FR-1: Starter list display
Any visitor can view the current Company Universe as explorable cards on the landing page without authentication.

**Consequences (testable):**
- Landing page renders all Phase 1 companies (CP, QSR, OTEX, SHOP) as cards with company name, ticker, and last-updated date, with no login required.
- Each card links directly to that company's overview page.

#### FR-2: Ticker search
A visitor can search for any ticker via a search input.

**Consequences (testable):**
- Searching a ticker within the current universe navigates to its overview page.
- Searching a ticker outside the current universe returns an explicit "not yet covered" message — never a silent failure, generic error, or fabricated result.

### 4.2 Quality & Health Lens *(Phase 1)*
**Description:** Computes the Piotroski F-Score and Altman Z-Score from XBRL-sourced Canonical Facts, with every sub-signal individually visible and traceable. Realizes UJ-1.

#### FR-3: Piotroski F-Score computation
The system computes a Piotroski F-Score (0–9) for each company in the universe using its most recent two consecutive fiscal years of Canonical Facts.

**Consequences (testable):**
- Each of the 9 binary signals (profitability, leverage/liquidity, operating efficiency) is individually computed and stored, not just the aggregate.
- The formula is versioned; a formula change creates a new version rather than silently overwriting history.
- If a required Canonical Fact is missing for a company/period, the affected signal is marked "insufficient data" rather than guessed or defaulted.

#### FR-4: Altman Z-Score computation
The system computes an Altman Z-Score for each company using its most recent fiscal year of Canonical Facts.

**Consequences (testable):**
- All 5 underlying weighted ratios (working capital/total assets, retained earnings/total assets, EBIT/total assets, market value of equity/total liabilities, sales/total assets) are individually computed and stored, not just the aggregate.
- Market value of equity is computed from a period-end closing price sourced from Tiingo (free tier) joined with EDGAR's `dei:EntityCommonStockSharesOutstanding` at fiscal-year-end — never a book-value substitute (see `foundational-decisions.md` D7 exception and architecture AD-11/AD-14). The closing price is the close on the last trading day on or before fiscal-year-end.
- The formula is versioned identically to FR-3.
- Companies outside the model's valid sector scope (financial-sector firms) are excluded from Altman computation entirely rather than shown a misleading score — Altman's original model is undefined for that capital structure (see `foundational-decisions.md` D6).
- A company in a structurally capital-intensive sector (e.g., pipelines/infrastructure) that is included in the universe carries an explicit interpretive caveat alongside its Altman score rather than a bare number (see `foundational-decisions.md` D6, ENB note).

#### FR-5: Quality/Health sub-signal display
A user can view each of the 9 Piotroski signals and each of the 5 Altman components individually, with pass/fail status (Piotroski) or contribution weight (Altman) and supporting Canonical Fact(s). Realizes UJ-1, UJ-2.

**Consequences (testable):**
- Each signal shows the specific values compared (e.g., "ROA 2024: 4.2% vs 2023: 3.1% → Pass").
- Each value links to its Provenance record (source filing and line item).

### 4.3 Integrity & Evidence Lens *(Phase 1)*
**Description:** Computes the Beneish M-Score and Sloan accruals ratio — the product's core differentiator — flagging earnings-quality concerns with full provenance. Realizes UJ-1, UJ-2.

#### FR-6: Beneish M-Score computation
The system computes a Beneish M-Score for each company using its most recent two consecutive fiscal years of Canonical Facts.

**Consequences (testable):**
- All 8 underlying indices (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA) are individually computed and stored.
- The formula is versioned identically to FR-3.
- Companies outside the model's valid sector scope (financial-sector firms) are excluded from Beneish computation entirely, for the same reason as the Altman exclusion in FR-4 (see `foundational-decisions.md` D6).

#### FR-7: Sloan accruals ratio computation
The system computes the Sloan accruals ratio for each company per fiscal year using its Canonical Facts.

**Consequences (testable):**
- Ratio computed via the balance-sheet approach using two consecutive balance sheets.
- Flagged as a high-accrual warning when it crosses the published threshold, with the threshold value stated explicitly (not just "high"/"low").

#### FR-8: Integrity sub-signal display & Provenance
A user can view each Integrity signal's inputs and its source filing line item. Realizes UJ-1, UJ-2.

**Consequences (testable):**
- Same provenance-linking pattern as FR-5.
- An explicit accounting-identity validation flag appears if a filing's reported figures fail a basic consistency check (e.g., balance sheet doesn't balance) — surfaced as a data-quality warning, never silently hidden.

### 4.4 Verdict & Company Overview *(Phase 1: partial; Phase 2: complete)*
**Description:** A single overview page per company showing a glanceable top-level Verdict synthesized transparently from whichever lenses are currently live, with expandable sub-factor breakdowns (the summary-first/drill-down-second pattern validated against Simply Wall St and Seeking Alpha). Realizes UJ-1.

#### FR-9: Company overview page
Each company in the universe has a dedicated overview page showing its Verdict and all currently-live lens scores.

**Consequences (testable):**
- The Verdict is a transparent side-by-side juxtaposition of each live model's own published, cited threshold classification — never a blended/weighted single score and never an LLM-invented number (architecture AD-12). Each model shows its own bands: Piotroski per its original paper (Strong 8-9, Weak 0-1, 2-7 shown as Middle/mixed — no invented cutoff); Altman >2.99 Safe / 1.81-2.99 Grey / <1.81 Distress; Beneish >-1.78; Sloan per its versioned formula-spec threshold. The band label is computed in the backend and stored; the frontend renders the stored label and never recomputes cutoffs (AD-8).
- Individual lens scores remain visible and clickable even when the Verdict is a synthesis; a user is never forced to accept only the summary.
- The page states explicitly which lenses are live vs. pending for that company (honest about Phase 1's partial coverage).

#### FR-10: Expandable sub-factor breakdown
A user can expand any lens score on the overview page to see its individual sub-signals inline, without navigating away. Realizes UJ-1, UJ-2.

**Consequences (testable):**
- Expansion happens in-page (accordion/expandable section), not a modal.
- Each sub-signal links onward to its full Methodology Page (FR-11).

### 4.5 Methodology Drill-Down *(Phase 1)*
**Description:** A dedicated page per Deterministic Score explaining its formula, the exact fields used, and its version. Realizes UJ-2.

#### FR-11: Methodology page per score
Each Deterministic Score (Piotroski, Altman, Beneish, Sloan, and later Value/Growth metrics) has a dedicated methodology page.

**Consequences (testable):**
- The page states the formula, the exact XBRL concepts/fields mapped to each formula input, and the formula version in use.
- The page links to the original academic source of the model (e.g., the original Piotroski 2000 paper).

### 4.6 AI Score Explanation *(Phase 1)*
**Description:** A narrow, direct LLM wrapper (per `foundational-decisions.md` D7 — no LangChain/LangGraph here) that narrates already-computed scores and verdicts with citations. Realizes UJ-1, UJ-2.

#### FR-12: Cited narrative explanation
A user can request a plain-language explanation of any computed score or the overall Verdict. The explanation is generated deterministically-first: a template renders directly from already-computed `score_results`/Canonical Facts, and an LLM — if used at all — only rewrites/polishes that already-correct text, never originating a claim, number, or citation (architecture AD-7).

**Consequences (testable):**
- The explanation text is produced by a deterministic template from already-computed scores/Canonical Facts; the LLM is never in the computation loop and never introduces a claim, number, or citation not already present in the source data.
- The LLM receives only already-computed Canonical Facts/scores as input — it never computes or alters a number.
- The Phase-1 LLM is a small, cheap model (default Claude Haiku 4.5) behind an env-configured key, a narrow direct wrapper — no LangChain/LangGraph (see `foundational-decisions.md` D7, architecture AD-21).
- Every explanation includes inline Citations to the specific Provenance record(s) it drew from.
- If a statement cannot be grounded in a Citation, it is omitted rather than asserted uncited.

### 4.7 Comparison *(Phase 1, grows with lenses)*
**Description:** Side-by-side comparison of two or more user-selected companies, showing whichever lenses are live at the time. Realizes UJ-3.

#### FR-13: Add to comparison
A user can add any company they've viewed to an in-session Comparison set from its overview page.

**Consequences (testable):**
- The comparison set persists only for the current browser session (no auth, no server-side persistence in v1 — consistent with `foundational-decisions.md` D4).
- A minimum of 2 and a maximum of 4 companies can be compared at once (confirmed 2026-07-17).

#### FR-14: Side-by-side comparison view
A user can view added companies' Verdicts and all currently-live lens scores in parallel columns.

**Consequences (testable):**
- The view shows exactly the lenses live in the current phase for each company (Phase 1: Integrity + Quality only), consistent with FR-9's phase honesty.
- Differences beyond a stated threshold are visually highlighted (e.g., diverging pass/fail signals).

### 4.8 Filing Q&A *(Phase 2 — directional)*
**Description:** LangGraph-orchestrated, citation-grounded Q&A over a company's filings, with a self-verifying citation loop (per `foundational-decisions.md` D7). Realizes UJ-2.

#### FR-15: Cited filing Q&A *(directional, detailed at architecture stage)*
A user can ask a free-text question about a company's filings and receive a cited, evidence-checked answer, or an explicit "insufficient evidence" response rather than an unsupported claim.

**Consequences (testable, to refine at architecture stage):**
- Every claim in an answer carries a Citation to a specific filing passage; a claim that cannot be grounded is omitted or replaced with an explicit "insufficient evidence" statement (same rule as FR-12).
- Orchestrated via LangGraph with a self-verifying citation loop (see `foundational-decisions.md` D7) — the verification step is a real, testable stage, not decoration.

### 4.9 Value Lens *(Phase 2 — directional)*
**Description:** DCF, reverse DCF, Graham Number, yields, and selected peer multiples — with assumptions and sensitivity always shown, never a bare "fair value" number.

#### FR-16: Valuation metrics *(directional, detailed at architecture stage)*
The system computes valuation metrics per company with stated assumptions and sensitivity ranges.

**Consequences (testable, to refine at architecture stage):**
- No valuation output is ever presented as a bare point estimate — assumptions and a sensitivity range accompany every figure.
- Missing-input handling follows the FR-3 "insufficient data" pattern: absent Canonical Facts produce an explicit gap, never a silently defaulted assumption.

### 4.10 Growth Lens *(Phase 2 — directional)*
**Description:** Revenue/EPS growth, margin trajectory, FCF growth, ROIC, dilution, with qualitative guidance/sentiment as supporting evidence only — never a standalone score. Includes historical trend presentation across available fiscal years and a small number of high-value financial visualizations (custom-built per `foundational-decisions.md` D7 — no off-the-shelf widgets), carried forward from the source consolidation review's Phase 2 deliverables.

#### FR-17: Growth trajectory metrics *(directional, detailed at architecture stage)*
The system computes growth trajectory metrics per company across available fiscal years and presents them as historical trends.

**Consequences (testable, to refine at architecture stage):**
- Trend depth honestly reflects each company's available history (e.g., OTEX's multi-decade view vs. SHOP's shorter window per `foundational-decisions.md` D6) — the UI states the coverage window rather than implying uniform depth.
- Missing-period handling follows the FR-3 "insufficient data" pattern.

### 4.11 Thesis Journal & Re-verification *(Phase 2/3 — directional)*
**Description:** Lets a user save a written investment thesis for a company, auto-attached to the live lens scores/facts at that moment, then diffs those specific cited facts against current values on return. Differentiated from Simply Wall St's Narratives (price/fair-value-only) by re-checking the user's actual cited evidence, not just price movement. Realizes UJ-4.

#### FR-18: Thesis save and re-verification *(directional, detailed at architecture stage)*
A user can save a Thesis for a company; on return, the system produces a Thesis Diff against currently live values.

**Consequences (testable, to refine at architecture stage):**
- Persisted browser-locally in v1 (no auth), consistent with `foundational-decisions.md` D4.
- The Thesis Diff is presented per-claim/per-metric, not as a single "something changed" flag.

### 4.12 Notifications & Deep Research Requests *(Phase 3 — directional)*
**Description:** A single notification system with two triggers — Thesis re-verification becoming available, and Deep Research Request fulfillment — delivered by email to an address the user provides, with no account or password required. Realizes UJ-4, UJ-5. Builds on the async infrastructure already planned for Phase 3 (scheduled ingestion, queue/worker processing, retries) and the Filing Q&A engine from Phase 2, rather than introducing a separate work stream.

#### FR-19: Thesis re-verification notification
When a new relevant filing is ingested for a company with a saved Thesis, the system emails the address tied to that Thesis with a link to the Thesis Diff. Realizes UJ-4, UJ-5.

**Consequences (testable):**
- The trigger fires once per new filing per Thesis, not repeatedly.
- The email contains a summary of what changed, not just a bare "check the app" link — full detail lives in-app.

#### FR-20: Deep research request submission
A user can submit an open-ended research question about a company, along with an email address, to be answered by an asynchronous, more thorough version of the Filing Q&A agent. Realizes UJ-5.

**Consequences (testable):**
- The request is queued with a stated SLA (e.g., "within 24 hours") shown to the user at submission time.
- The same citation-grounding rule as FR-12/FR-15 applies: if evidence is insufficient, the delivered result says so explicitly rather than presenting a weak answer as solid.
- No account or password is created — only an email address, tied to the request.

#### FR-21: Deep research request fulfillment notification
When a Deep Research Request is completed, the system emails the requesting address with the cited result (or an explicit insufficient-evidence notice). Realizes UJ-5.

**Consequences (testable):**
- Delivered via a real transactional email provider (e.g., SES/Postmark/Resend) — not a placeholder.
- The email includes the citations themselves, not just a "log in to see your answer" teaser.

**Notes:** Email-only identity capture and email-only delivery channel were chosen deliberately over full auth or in-app-only notifications, to keep the deviation from `foundational-decisions.md` D4's no-auth stance as small as possible while still exercising real queue/worker/notification-delivery engineering. `[NOTE FOR PM]` Revisit whether the same email-capture mechanism should be reused if a future startup-optional pivot needs persistent accounts.

## 5. Non-Goals (Explicit)

- **Never investment advice.** The system never tells a user what to do — it presents evidence and lets the investor form their own thesis. This is permanent, not a v1 limitation.
- **No LLM-generated canonical scores, ever.** Every number, score, and threshold is computed deterministically. The LLM explains and cites; it never originates a figure (see `foundational-decisions.md` D5, D7).
- **No brokerage integration, trade execution, or broker/fee comparison** in any current phase. If ever added, it would be an architecturally separate feature, never stitched into a company's verdict page (see research findings logged in `.memlog.md`).
- **No full market coverage.** Not S&P 500, not broad TSX/TSXV — the Company Universe stays deliberately narrow and honestly labeled.
- **No user accounts or passwords**, beyond the minimal email-only capture introduced in Phase 3 for Notifications (§4.12). No login, no persistent multi-device sessions.
- **No off-the-shelf charting widgets** (e.g., TradingView) — visualizations are custom-built over ThesisTrace's own computed data (see `foundational-decisions.md` D7).
- **No IFRS-reporting companies** in the current Piotroski/Altman/Beneish/Sloan formula set, until (if ever) an IFRS-aware calculation-mapping layer is built. Not scheduled to any phase yet (see `foundational-decisions.md` D6).
- **No native mobile app.** Web-only (responsive), confirmed 2026-07-17 as a deliberate product-scope choice, not just a stack side effect — the research-session use case is desktop-leaning.
- **No broad news/sentiment aggregation via multiple paid data providers.** `[NON-GOAL for MVP]` `[NOTE FOR PM]` A lighter version — notifying on new 8-K material-event filings for a tracked/Thesis company — reuses the existing EDGAR pipeline and is a plausible future add-on; the heavier version (general news, analyst ratings, sentiment) would require new paid data providers (conflicting with the single-provider-first principle in D7) and is fully commoditized by existing ticker apps, so it isn't planned at all. Revisit only if the cheap 8-K version proves valuable and there's appetite for more.
- **No sector heatmap, no draggable/resizable dashboard UI.** Carried forward from the original consolidation review's defer-list — not planned in any phase, same treatment as full market coverage above.
- **No formal accessibility (WCAG) compliance target.** Given the single-primary-user, hobby-scale posture, this isn't a v1 commitment. `[NOTE FOR PM]` Revisit if the audience ever expands beyond the primary user (see D2's secondary 20% audience).
- **No formal performance, uptime, or security NFR targets for v1.** A deliberate omission at hobby/solo scale, not an oversight — correctness (SM-1) is the quality bar that matters here. Operational rigor (monitoring, alerts, rollback) is scheduled engineering-learning work in Phase 4, per the source consolidation review's delivery plan, and NFR targets should be set then if the startup-optional path (D4) is ever exercised.
- **No SEDAR+ / TSX-only-listed (non-EDGAR) Canadian companies.** Out of scope for the foreseeable roadmap given the EDGAR-only data strategy (`foundational-decisions.md` D6) — would require an entirely separate ingestion pipeline and regulatory-filing format. Not scheduled to any phase.

## 6. MVP Scope

### 6.1 In Scope (Phase 1)

- Company Universe limited to CP, QSR, OTEX, SHOP (FR-1, FR-2).
- Quality & Health Lens: Piotroski F-Score, Altman Z-Score (FR-3, FR-4, FR-5).
- Integrity & Evidence Lens: Beneish M-Score, Sloan accruals ratio (FR-6, FR-7, FR-8).
- Verdict & Company Overview, showing only the two live lenses above, honestly labeled as partial (FR-9, FR-10).
- Methodology Drill-Down for every live score (FR-11).
- AI Score Explanation — narrow direct wrapper, cited (FR-12).
- Comparison across 2–4 companies, showing whichever lenses are live (FR-13, FR-14).

### 6.2 Out of Scope for MVP

- **Filing Q&A** (FR-15) — deferred to Phase 2; needs pgvector/RAG infrastructure not yet built.
- **Value Lens** (FR-16) and **Growth Lens** (FR-17) — deferred to Phase 2, per the lens-sequencing decision in `foundational-decisions.md` D5.
- **Thesis Journal & Re-verification** (FR-18) — deferred to Phase 2/3; depends on Filing Q&A maturity and browser-local persistence design. `[NOTE FOR PM]` This is the feature most directly tied to the product's name and core differentiation — revisit for earlier scheduling if timeline permits.
- **Notifications & Deep Research Requests** (FR-19–FR-21) — deferred to Phase 3; depends on Filing Q&A maturity and async queue/worker infrastructure.
- **Broader Company Universe (5–10 companies)** — deferred to Phase 2.
- **IFRS company support** — deferred indefinitely, no committed phase; requires a new calculation-mapping layer (see Non-Goals).
- **News/corporate-action notifications** — deferred indefinitely (see Non-Goals `[NOTE FOR PM]`).
- **Brokerage referral/comparison, auth beyond email capture, native mobile app** — not planned in any phase (see Non-Goals).

## 7. Success Metrics

**Primary**
- **SM-1:** Score correctness — 100% of Piotroski, Altman, Beneish, and Sloan scores computed for the Phase 1 Company Universe match a hand-verified or published golden dataset, enforced by regression tests. Validates FR-3, FR-4, FR-6, FR-7.
- **SM-2:** Real use — ThesisTrace informs at least one real investment decision made by the primary user (user zero) within 3 months of Phase 1 launch (window confirmed 2026-07-17). Validates FR-9.

**Secondary**
- **SM-3:** Engineering showcase value — at least one technical reviewer (e.g., a hiring manager or peer engineer in the financial-engineering space) engages with the Methodology Drill-Down or Filing Q&A feature and it holds up to scrutiny. Validates FR-11, FR-15.
- **SM-4:** Genuine stickiness — the primary user returns to use Comparison or the Thesis Journal more than once, unprompted, after initial launch. Validates FR-13/FR-14, FR-18.

**Counter-metrics (do not optimize)**
- **SM-C1:** Company Universe breadth — do not expand the number of covered companies as a vanity metric before SM-1 (correctness) is solid. A wider but shakier universe undermines the entire premise. Counterbalances any temptation to prioritize coverage over correctness.
- **SM-C2:** Notification volume or open rate — do not optimize the number of notifications sent or opened. Notifications (FR-19–FR-21) exist to serve a genuine decision moment, not to maximize re-engagement. Counterbalances SM-4 and the risk of treating Notifications as an engagement-growth lever.

## 8. Open Questions

1. **Golden-dataset sourcing** — where do hand-verified/published Piotroski, Altman, Beneish, and Sloan scores for CP, QSR, OTEX, and SHOP come from, and how is the dataset kept current as new filings arrive? Blocks SM-1 measurement.
2. ~~Amended/restated filings policy~~ — **resolved 2026-07-19 by architecture AD-6:** an amendment triggers a new append-only `score_run` referencing the new `canonical_facts`; the prior run is marked superseded, never deleted or mutated. The "current" score is the latest non-superseded run.
3. **Not-investment-advice disclaimer** — **partially resolved 2026-07-22:** shipped as a persistent site-wide footer (every page, via `frontend/app/layout.tsx`) plus a one-line caption on the Verdict section of the company page (`frontend/app/company/[ticker]/page.tsx`), since that's the surface most readable as a buy/sell signal. Wording/placement is a product-copy call, not a legal one — **whether Canada-specific legal review is warranted remains open**, unresolved by this change.
4. ~~Monthly cost ceiling~~ — **resolved 2026-07-17: ~$25/month** total for hosting + LLM spend. Forces free/hobby tiers (Vercel free, Supabase free tier, modest LLM API usage) — a binding constraint for the architecture phase.
5. **Deep Research Request SLA** — should the SLA be a fixed window (e.g., 24 hours) for every request, or vary by question complexity/cost? Affects queue design and user-facing copy for FR-19.
6. **Thesis Journal persistence resilience** — browser-local storage (FR-18) means a cleared cache or a new device loses saved Theses. Acceptable for v1, or does it need lightweight export/import?
7. **Email data handling** — what retention/deletion policy applies to emails collected for Notifications (FR-19–FR-21), and is an explicit privacy stance needed even at hobby scale?
8. **Universe expansion process** — when Phase 2 grows the Company Universe to 5–10 companies, does it repeat the manual EDGAR validation done for D6, or become an automated screening step?
9. **Lens sub-metric depth** — the original consolidation review named additional sub-metrics per lens beyond the four named academic models (e.g., debt maturity concentration, receivables-vs-revenue, cash-vs-earnings, trajectory-over-level rules). Are these folded into Phase 2 lens-depth work, or dropped from the roadmap entirely?

## 9. Assumptions Index

All three assumptions raised during drafting were explicitly confirmed on 2026-07-17 and promoted to firm requirements; none remain open:

- §4.7 (FR-13) — maximum of 4 companies in a single Comparison: **confirmed**.
- §7 (SM-2) — 3-month window for the "real use" success metric: **confirmed**.
- §5 (Non-Goals) — web-only, no native mobile app, as a deliberate product-scope choice: **confirmed**.
