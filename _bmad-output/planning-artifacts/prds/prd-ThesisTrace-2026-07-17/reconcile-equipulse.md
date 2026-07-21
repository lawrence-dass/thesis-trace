# Reconciliation: equipulse README vs. ThesisTrace PRD

**Input reconciled:** `/Users/lawrence/Documents/projects/portfolio_projects/equipulse/README.md`
**Against:** `/Users/lawrence/Desktop/ThesisTrace/_bmad-output/planning-artifacts/prds/prd-ThesisTrace-2026-07-17/prd.md`
**Also consulted:** `/Users/lawrence/Desktop/ThesisTrace/_bmad-output/planning-artifacts/foundational-decisions.md` (D4, D6, D7 — the PRD's stated rationale chain)

## 1. Primary decision under test: TradingView / off-the-shelf charting exclusion

**Verdict: Reflected. No gap.**

equipulse is a public dashboard built explicitly around TradingView script-embed widgets (candlestick charts, ticker widgets) — README calls this out as its core external dependency ("TradingView powers the dashboard and stock detail widgets").

The PRD carries the exclusion decision through cleanly, at three levels:

- `foundational-decisions.md` D7 names equipulse explicitly and gives the reasoning: "TradingView widgets render off-the-shelf ticker charts, not custom visualizations over ThesisTrace's own computed data... wrong fit, and would duplicate an existing portfolio piece." It commits to Recharts/visx instead.
- PRD §2.2 (Non-Users v1): "Day traders / technical (chart-pattern) analysts — no candlestick tools, no technical indicators, no TradingView-style widgets (see `foundational-decisions.md` D7)."
- PRD §5 (Non-Goals): "No off-the-shelf charting widgets (e.g., TradingView) — visualizations are custom-built over ThesisTrace's own computed data (see `foundational-decisions.md` D7)."

This is a textbook case of a decision made during discovery (comparing against equipulse) surviving intact into both the traceable foundational-decisions doc and the PRD's non-goals/non-users, with correct cross-referencing. Nothing to fix here.

## 2. Other equipulse patterns — checked for relevance and acknowledgment

equipulse's README states four other load-bearing patterns beyond TradingView: (a) public-first, no-auth posture, (b) browser-local persistence for watchlist and dashboard layout, (c) Finnhub-backed stock search, (d) a draggable/resizable widget dashboard as the landing experience. Each was checked against the PRD.

### 2a. Public-first / no-auth stance — adopted, but not tied back to equipulse as precedent

ThesisTrace's PRD independently arrives at the same no-auth posture equipulse uses: UJ-1 entry state is "Unauthenticated, first visit, landing page directly (no login anywhere in v1)"; §5 Non-Goals states "No user accounts or passwords, beyond the minimal email-only capture introduced in Phase 3." The PRD cites `foundational-decisions.md` D4 for this ("consistent with `foundational-decisions.md` D4" appears at FR-12 and FR-17).

Gap: D4 in foundational-decisions.md ("End-state posture: portfolio-complete, startup-optional architecture") is a general architecture-cost argument ("do not build auth... early") — it does not mention equipulse and was not framed as reuse of/divergence from equipulse's public-first pattern. The two documents converge on the same design by coincidence-of-reasoning rather than by explicit precedent-check, unlike the TradingView decision which explicitly cites equipulse. Not a functional problem, but if the goal of this reconciliation step is "was equipulse actually used as prior art beyond charts," the no-auth convergence was not documented as such.

### 2b. Browser-local persistence for watchlist / layout — partially diverged, unacknowledged

equipulse persists two things client-side, indefinitely (until cache clear): a `watchlist` (arbitrary user-picked tickers) and a `dashboard_layout` (widget grid arrangement).

ThesisTrace has no direct analog to either:

- **No watchlist feature at all.** The PRD's closest concepts are Comparison (FR-12/13) and Thesis (FR-17). Comparison is explicitly *session-scoped only* ("persists only for the current browser session... no server-side persistence in v1" — FR-12), i.e. it does NOT survive a browser restart the way equipulse's watchlist does. Thesis (FR-17) is persisted browser-locally and does survive restarts, but it's a fundamentally different object (a written rationale + attached facts, not a saved list of tickers to revisit).
- **No dashboard-layout equivalent.** ThesisTrace has no customizable/draggable widget grid — reasonable, since Phase 1 is a fixed 4-company universe rather than an open market dashboard, so there's no obvious "layout" to persist.

Neither omission looks like an oversight given the narrower scope (a 4-company fixed universe doesn't need a watchlist the way an open market dashboard does), but the PRD and foundational-decisions.md never explicitly say "we're not carrying over equipulse's watchlist pattern, and here's why" the way D7 did for TradingView. Worth a one-line acknowledgment if this reconciliation gets folded back into foundational-decisions.md, purely for future-reader traceability — not a blocking gap.

### 2c. Finnhub-backed broad-market search — diverged, unacknowledged

equipulse's search (`SearchCommand` + `finnhub.actions.ts`) hits a live external API to resolve arbitrary tickers/company names across the public market.

ThesisTrace's FR-2 ("Ticker search") is scoped only to the fixed Phase 1 Company Universe (CP/QSR/OTEX/SHOP) — searching outside that set returns an explicit "not yet covered" message rather than falling through to a live market data provider. This is consistent with the narrow-universe, single-provider-first principle referenced elsewhere in foundational-decisions.md (D7's "conflicting with the single-provider-first principle"), but that principle is invoked for the news/sentiment non-goal (§5), not explicitly connected to why ThesisTrace's search doesn't (and Phase-2-forward, when the universe grows to 5–10 companies per Open Question 8, might not need to) use a Finnhub-style broad-market lookup like equipulse's. Again, a reasonable and likely-intentional divergence, but not one the PRD or foundational-decisions.md states outright as a deliberate non-reuse of equipulse's pattern.

### 2d. Draggable/resizable public dashboard as landing UI — diverged, unacknowledged (lowest concern)

equipulse's landing experience is a drag/resize widget grid. ThesisTrace's landing page (FR-1) is a static card list of the Company Universe. This is a sensible divergence given the very different content (forensic scores vs. price widgets) and isn't the kind of decision that needs equipulse-specific reconciliation — flagged only for completeness.

## Summary judgment

The one decision this reconciliation step was specifically asked to verify — TradingView/charting-library exclusion, motivated by not duplicating equipulse and fitting forensic/fundamental visualization needs — is fully and correctly reflected in the PRD, with proper traceability back through `foundational-decisions.md` D7.

The secondary ask (other equipulse patterns relevant to ThesisTrace's design) surfaces three patterns (no-auth, browser-local persistence/watchlist, Finnhub search) where ThesisTrace's PRD lands on a reasonable but *independently derived* answer rather than an answer explicitly checked against equipulse the way TradingView was. None of these look like design mistakes — the divergences are well justified by ThesisTrace's much narrower fixed-universe scope — but none are recorded as "considered equipulse's approach, diverged because X," so a future reader auditing prior-art usage would not be able to tell reuse-by-coincidence from reuse-by-decision for these three items.
