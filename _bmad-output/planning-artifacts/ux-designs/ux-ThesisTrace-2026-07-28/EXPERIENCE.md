---
name: ThesisTrace
status: final
sources:
  - {planning_artifacts}/foundational-decisions.md
  - {planning_artifacts}/prds/prd-ThesisTrace-2026-07-17/prd.md
  - {planning_artifacts}/prds/prd-ThesisTrace-2026-07-17/addendum.md
  - {planning_artifacts}/architecture/architecture-ThesisTrace-2026-07-19/ARCHITECTURE-SPINE.md
  - {planning_artifacts}/epics.md
  - {planning_artifacts}/ledgerlens-fundalens-consolidation-review.md
updated: 2026-07-29
---

# ThesisTrace — Experience Spine

> Web-only, responsive, no native app (D4/D7). Next.js 16 App Router + Tailwind v4, a small hand-rolled component kit (no shadcn/MUI — `DESIGN.md` is the from-scratch visual identity, not a delta on an inherited system). Primary audience: Daniel, a diligence-driven retail investor screening for genuine quality (D2; universe posture per D11), not a day trader (PRD §2.2 explicitly excludes candlestick/technical-analysis users). ~20% secondary audience: technical evaluators assessing the engineering (PRD §2.1) — same surface, different motivation, never a separate mode.

## Foundation

Single-surface responsive web app, server-rendered (Next.js App Router, data fetched server-side from the FastAPI read API — AD-8 presentation-only, the frontend never computes or reclassifies a score). No accounts, no login, no user-specific state beyond an in-session, browser-local comparison set (FR-13, D4 — no auth in Phase 1). `DESIGN.md` is the visual identity reference for every token named here.

Four Phase-1 surfaces, one per FR-1/9/11/14: landing, company overview, per-model methodology, comparison. A fifth conceptual surface — the explanation/citation layer (FR-12) — is not a separate page; it's embedded inline in the company overview's expandable breakdowns.

## Information Architecture

| Surface | Route | Reached from | Purpose |
|---|---|---|---|
| Landing | `/` | Direct visit, wordmark click | Company Universe starter list (FR-1) + ticker search (FR-2) |
| Company overview | `/company/{ticker}` | Landing card, search, methodology "back," compare row | Verdict juxtaposition (FR-9), expandable sub-factor breakdown (FR-10), data-quality warnings, cited explanation (FR-12) |
| Methodology | `/methodology/{model}` | "Methodology →" link inside an expanded sub-factor card | Formula, inputs, per-signal description, source citation (FR-11) |
| Comparison | `/compare?tickers=A,B,C,D` | "Add to comparison" → "Compare N" (2-4 companies) | Side-by-side Verdict/lens table, divergent rows highlighted (FR-13/FR-14) |

Not yet in scope (Phase 2/3, do not build surfaces for these, but the IA must not preclude them): Filing Q&A (FR-15), Value/Growth lenses (FR-16/17, already rendered as "pending lenses" text on the overview), Thesis Journal (FR-18, UJ-4), notifications (FR-19-21, UJ-5).

No sidebar, no nested app-shell — a single top nav bar (wordmark + one link back to the Universe) is sufficient for a 4-page, 4-company-universe product. `[ASSUMPTION]` A persistent nav should still grow one more affordance in this pass: a way to reach the in-progress comparison set from anywhere (currently only visible via the button on the page of a company already in it), since Daniel's UJ-3 requires building the set across multiple company visits.

## Voice and Tone

Microcopy. Brand voice and aesthetic posture live in `DESIGN.md.Brand & Style`.

| Do | Don't |
|---|---|
| "Not yet covered by ThesisTrace." (plain, no apology, no dead-end — PRD UJ-1 edge case) | "Oops! We couldn't find that ticker 😕" |
| "Each model's own published threshold classification, shown side by side — not a buy/sell recommendation." | Anything implying ThesisTrace recommends an action |
| "No manipulation flag" / "Low accruals (higher quality)" — the model's own band vocabulary, verbatim (AD-12) | Inventing friendlier synonyms for a band label that has to match the backend's cited classification exactly |
| Numbers in `tabular-nums` monospace, always with their unit/scale implicit from context (e.g. Piotroski is always "/9") | Rounding or reformatting a value the backend already computed (AD-8) |
| "Pending lenses (future phase): value, growth." — plain phase-honesty | Hiding what's missing, or a vague "coming soon" |

## Component Patterns

Behavioral. Visual specs live in `DESIGN.md.Components`.

| Component | Use | Behavioral rules |
|---|---|---|
| Verdict card | Company overview (grid of 4) | One per live model. Shows aggregate value, band badge (or applicability badge if excluded/caveated), a range visualization, and a one-line teaching caption. Never shows a bare number for `excluded_out_of_scope`/`computed_with_caveat` (AD-20) — the applicability badge always takes precedence over the band badge in that case. |
| Sub-factor card (expandable) | Company overview, one per category (Quality & Health, Integrity & Evidence) | Collapsed by default, shows model name + FY + aggregate + band inline in the summary row. Expands in-page (FR-10, no navigation) to list every signal with its `pass`/`fail`/`insufficient_data` badge (AD-16), its value, and its provenance. Never collapses a signal that failed — failing signals are exactly what Daniel is there to see (UJ-1). |
| Provenance citation | Inside every expanded signal | Every displayed value resolves to `(accession_number, canonical_concept, fiscal_year)` (AD-19). `[ASSUMPTION]` Promote from static text to an actual link out to the source SEC EDGAR filing (constructible client-side from CIK + accession_number — no backend change needed) — AD-19 already says "the frontend links to it," not yet fully realized. A value with no resolvable provenance is never displayed as fact (existing rule, keep). |
| Comparison table | `/compare` | 1 row per model, 1 column per company (2-4). A row whose companies' classifications diverge gets a highlighted background (existing behavior, keep) — this is the single most important visual signal on the page (UJ-3's climax is "seeing at a glance where they diverge"). |
| Add-to-Compare control | Company overview header | Toggle button + running count, session-scoped (`sessionStorage`, not persisted across sessions — a deliberate scope decision per the PRD addendum, not an oversight). Caps at 4, floors at 2 before the compare link activates. |
| Data-quality banner | Company overview, only when issues exist | One `caveat`-toned banner, above the Verdict section fold — never buried inside a collapsed card, since a data-quality issue can affect trust in the whole page. |
| Methodology reference card | Methodology page | Formula description, canonical-concept chips, per-signal description list, source citation. Read-only, no interaction beyond the incoming link from a sub-factor card. |

## State Patterns

| State | Surface | Treatment |
|---|---|---|
| No companies ingested yet | Landing | Card: "No companies available yet — the pipeline hasn't run for this environment." (existing, keep — honest about environment state, not a fake empty-state illustration) |
| Ticker outside the universe | Company overview | "Not yet covered by ThesisTrace." — no error styling, no dead end (PRD UJ-1 edge case, existing behavior, keep) |
| Backend unreachable | Any data-fetching page | "Backend unreachable." Plain, not a stack trace, not a generic Next.js error boundary. |
| Model excluded for this company | Verdict card / sub-factor card | `excluded_out_of_scope` badge instead of a bare score (AD-20 — e.g. a financial-sector company excluded from Altman/Beneish per D6). Caption still present so it reads as "this doesn't apply here," not "broken." |
| Model result caveated | Verdict card / sub-factor card | `computed_with_caveat` badge alongside the value (AD-20 — e.g. a capital-intensive firm's Altman). Never a bare number pretending the caveat doesn't exist. |
| Signal `insufficient_data` | Expanded sub-factor breakdown | `pending`-toned badge, never coerced to a defaulted pass/fail 0 (AD-16). The absence itself is informative — shown, not hidden. |
| Fewer than 2 companies in the comparison set | `/compare` | "Add at least 2 companies (max 4) to compare." (existing, keep) |
| Cold/first load of a data-heavy page | Company overview | `[ASSUMPTION]` No loading skeleton currently exists (Next.js server-rendering means the whole page waits on the fetch) — for a page this data-dense, add a skeleton matching the Verdict-grid + card-list shape rather than a blank flash, since AD-6 and score computation are synchronous per-request from the reader's perspective. |

## Interaction Primitives

Primarily mouse/touch, read-heavy, not keyboard-power-user-first (Daniel is an investor doing research, not a developer in a tool all day — contrast with a Linear/Drift-style keyboard-first product). Still:

- **Disclosure**: native `<details>`/`<summary>` for sub-factor expand/collapse (FR-10) — keep; it's free accessibility (keyboard-operable, screen-reader-announced) and matches the "in-page, no navigation" requirement exactly.
- **Search**: type a ticker, `Enter` or click Search navigates directly to `/company/{ticker}` — no live-filtering autocomplete needed given the fixed 4-company universe (FR-2 is deliberately scoped, not a broad-market search per the PRD addendum's equipulse-divergence note).
- **Add to Compare**: single click toggles membership; no drag, no multi-select mode. `[ASSUMPTION]` Consider a lightweight persistent affordance (e.g. a small floating count-badge, not a full sidebar) so the in-progress comparison set is visible/reachable from the landing page and other company pages too, not only from a page of a company already added.
- **Provenance**: `[ASSUMPTION]` clicking a citation opens the source filing in a new tab (`target="_blank"`) — leaving ThesisTrace to verify a claim is the point (PRD UJ-2), not a dead end to avoid.
- **Banned**: infinite scroll (the universe is 4 companies, pagination is moot), hover-only affordances on touch viewports, any control whose only path to a value is a tooltip (values must be visible or one tap away, never hover-locked — this is a citation-driven trust product, not allowed to hide the evidence behind a hover).

## Accessibility Floor

Behavioral. Visual contrast lives in `DESIGN.md`.

- WCAG 2.2 AA across the whole responsive web surface, including every tri-state signal color pairing (pass/fail/caveat/pending/excluded) at both text-on-background and badge-fill-on-background contrast ratios — this is a financial-trust product; a colorblind user must be able to tell `pass` from `fail` without color alone, which is why every existing Badge already pairs an icon with the color (keep and extend this discipline to any new visualization).
- Screen reader announces page/surface on navigation: "Company overview, {ticker}, {name}" / "Methodology, {model}" / "Comparison, {N} companies."
- `<details>` disclosure triangles are keyboard-operable and announce expanded/collapsed state natively — no custom accordion JS to reimplement this.
- Tab order matches visual reading order on every surface; focus rings visible at AA contrast against `{colors.surface}` (or the dark-mode equivalent, if adopted — see `DESIGN.md`).
- No information conveyed by color alone anywhere a badge/icon pairing already exists; the same rule extends to any new gauge/chart component — a color-blind reader must be able to read a zone/classification from shape or label, not hue alone.
- Every data table (comparison page) has real `<th>` headers with scope, not styled `<td>`s — screen readers must announce "Piotroski F-Score, SHOP: Middle," not a bare cell.

## Responsive & Platform

| Breakpoint | Behavior |
|---|---|
| `≥ lg` (1024px+) | Verdict grid: 4 columns. Company-universe grid: 4 columns. Full-width comparison table. |
| `md` (768–1023px) | Verdict grid: 2 columns. Company-universe grid: 2 columns. Comparison table scrolls horizontally within its card (existing `overflow-x-auto`, keep). |
| `< md` (`sm`) | Everything single-column. Comparison table still horizontally scrollable (min-width forces this, existing behavior). |

Web-only, no native mobile app (D4/D7) — the product must still be fully usable on a phone browser (Daniel checking a name while away from his desk is a plausible real session), just not optimized as the primary surface.

## Key Flows

Verbatim from the PRD (§2.3) — this spine does not restate them with different names; it specifies how each beat is realized on-surface. Persona: **Daniel**, diligence-driven retail investor (D2; D11).

### Flow 1 — UJ-1: Daniel checks whether an industrial name's numbers actually hold up

1. Unauthenticated, first visit, lands on `/`. Sees the Phase-1 starter list (CP, QSR, OTEX, SHOP) as explorable cards — no quiz, no gate.
2. Clicks Canadian Pacific Kansas City → `/company/CP`. Sees the Verdict grid up top (nutshell classification per model), expandable sub-factor breakdowns underneath.
3. Expands the Integrity & Evidence category specifically — sees each Beneish/Sloan signal's pass/fail status, tied to the actual line item in CP's real EDGAR filing via its provenance citation.
4. **Climax:** He can see, in plain terms backed by real filing citations, whether CP's reported numbers are trustworthy — not an opaque score he has to just believe.
5. **Resolution:** Confident either way, closes the tab or clicks into QSR to compare.
6. **Edge case:** Searches a ticker outside the Phase-1 universe — `/company/{ticker}` renders "Not yet covered by ThesisTrace," not an error.

### Flow 2 — UJ-2: Daniel, in skeptical mode, goes under the hood

1. Continues from Flow 1's climax, still on `/company/CP`.
2. Clicks "Methodology →" from an expanded sub-factor card → `/methodology/beneish`.
3. Sees the actual formula description, the specific canonical-concept chips it pulled, and the per-signal descriptions.
4. Optionally reads the cited explanation text embedded in the overview's expanded card (FR-12) — narration grounded in the same citations, never a number the LLM invented.
5. **Climax:** Full trust established, or a specific, well-founded doubt — nothing hidden behind a black-box number.
6. **Resolution:** Returns to `/company/CP` with either confirmed trust or an articulable concern.

### Flow 3 — UJ-3: Daniel decides between two candidates he's already vetted

1. On `/company/QSR` (viewed after CP earlier in the session), clicks "Add to comparison."
2. Navigates to `/company/CP`, clicks "Add to comparison" there too. Button now reads "Compare 2."
3. Clicks through → `/compare?tickers=QSR,CP`. Sees both companies' Verdicts in parallel columns.
4. **Climax:** Sees at a glance where they diverge — e.g. one has a cleaner Integrity row (highlighted background marks the divergence), the other close but with one flagged accrual signal.
5. **Resolution:** Picks a direction with a specific, articulable reason, or digs into the one flagged signal (back to Flow 1's expand behavior) before deciding.

## Inspiration & Anti-patterns

From the competitive/design research pass (Bloomberg Terminal, Koyfin, Simply Wall St, TipRanks, Finchat.io, Morningstar, YCharts, stockanalysis.com):

- **Lifted from Morningstar: achromatic, disciplined rating display.** The Star Rating renders in plain black regardless of score, with solid vs. hollow stars communicating a *data-sufficiency* distinction (3+ years of history vs. not) rather than a good/bad judgment. ThesisTrace's own `insufficient_data` badge (State Patterns, above) already does the equivalent — showing absence as its own explicit state rather than defaulting to pass/fail — and this research confirms that's the right institutional pattern, not an ad hoc choice.
- **Lifted from stockanalysis.com: chrome-free density, no upsell/dead-end interruptions.** Reviewers single out the absence of pop-ups, gates, or upsell modals as what makes it feel fast and trustworthy for research use. Directly reinforces the existing "Not yet covered by ThesisTrace" / "No manipulation flag" plain-copy rules in Voice and Tone above — no dead ends, no false cheerfulness, ever.
- **Lifted from Koyfin/Bloomberg, decoupled from their trading context: a command bar reads as a serious tool.** Both use a `/`-triggered command surface (`ticker <enter> function <enter>`) as their power-user signature. ThesisTrace's existing ticker search already gestures at this; **not** extended into a full command-key system, since (per Interaction Primitives, above) Daniel is doing research, not trading, and a Bloomberg/Koyfin-style hotkey culture would misrepresent the product's audience.
- **Rejected — Simply Wall St's Snowflake / TipRanks' Smart Score as a single "hero visualization."** Both make one colorful composite graphic the product's signature — exactly the pattern `DESIGN.md`'s Components section rejects for the Gauge redesign (a tick-marked band, not a radial dial) and exactly what AD-12's per-model Verdict juxtaposition already forbids at the data-model level. Confirms, doesn't just parallel, that existing rule.
- **Rejected — Bloomberg's amber-on-black CRT aesthetic and physical color-coded keyboard.** A trading-desk signifier, not an equity-research one; would misrepresent ThesisTrace's audience (PRD §2.2 explicitly excludes day traders) even if visually striking.
- **Rejected — Finchat.io's chat-first interaction paradigm as the primary surface.** Conversational/prompt-driven UI is a different product shape entirely (an AI-analyst chat, not a citation-grounded read surface) and would undercut FR-12's requirement that explanations stay grounded in the same visible citations a reader can independently verify — a chat transcript is a worse home for that than an inline expandable card.

Already-decided anti-patterns from the PRD/foundational-decisions, not from research:
- **Rejected — candlestick charts, technical indicators, TradingView-style widgets**: explicitly out of scope (D7, PRD §2.2) — the audience is fundamentals-based, not technical-analysis-based.
- **Rejected — a blended single "buy/sell" score**: Verdict is always per-model juxtaposition, never averaged (AD-12) — an enterprise redesign must not accidentally introduce a composite score for visual simplicity.
- **Rejected — persistent cross-session watchlist for Comparison**: deliberately session-only (FR-13, PRD addendum §A3) — the Thesis Journal (FR-18, Phase 2) is the feature that gets real persistence, not Comparison.
- **Rejected — suitability quiz / onboarding gate**: off-pattern for this category per the PRD addendum's onboarding-pattern research; users drop straight into search/dashboard.
