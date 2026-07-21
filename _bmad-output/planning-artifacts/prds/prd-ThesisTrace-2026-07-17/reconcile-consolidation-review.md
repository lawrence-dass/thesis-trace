# Reconciliation: LedgerLens/Fundalens Consolidation Review vs. PRD + Addendum + Foundational Decisions

**Source:** `/Users/lawrence/.codex/.chatgpt-projects/g-p-6a582c0cd0608191bbb731d8052a7041/ledgerlens-fundalens-consolidation-review.md`
**Checked against:** `prd.md`, `addendum.md`, `foundational-decisions.md` (all in `_bmad-output/planning-artifacts/` and `prds/prd-ThesisTrace-2026-07-17/`)

Per instructions, the four-phase delivery plan, the Value/Growth/Quality/Integrity lens framework, and the tech-stack recommendations are treated as already reflected and are NOT re-flagged below except where a specific sub-item within them vanished.

---

## Gap 1 — Altman Z-Score has no Functional Requirement anywhere

`foundational-decisions.md` D5 states Phase 1 covers "Piotroski, Altman, Beneish, Sloan — fully mechanical from XBRL," and the source's Quality/Health lens list names Altman Z-Score explicitly. But in `prd.md` §4.2 "Quality & Health Lens (Phase 1)," only Piotroski is implemented (FR-3, FR-4). There is no FR anywhere in the document that computes, stores, versions, displays sub-signals for, or provides a Methodology Page for Altman Z-Score — unlike Piotroski (FR-3/4), Beneish (FR-5), and Sloan (FR-6). FR-10 (Methodology page per score) lists "Piotroski, Altman, Beneish, Sloan" as a set but no FR actually produces an Altman score to document. This is a real functional gap even though the model is *named* in the locked decisions doc — naming it there doesn't give it requirements, testable consequences, or MVP scope inclusion the way its three siblings got.

## Gap 2 — "Mature UX and accessibility planning" (a named Fundalens strength to preserve) is entirely absent

The source explicitly lists "mature UX and accessibility planning" as a Fundalens strength to carry forward into the consolidated product. None of the PRD, addendum, or foundational-decisions mentions accessibility, WCAG, keyboard navigation, screen-reader support, or any accessibility consideration at all — not even as an open question or assumption. This is a clean qualitative drop: a named strength with no trace downstream.

## Gap 3 — SEDAR+ / TSX-only PDF-extraction direction has vanished without a decision trail

The source's Canadian data strategy names "SEDAR+ filings and limited PDF extraction for TSX-only companies" as part of the plan, and the four-phase delivery plan lists a "limited SEDAR+ extraction experiment" explicitly under Phase 3. Neither SEDAR nor TSX-only PDF extraction appears anywhere in the PRD, addendum, or foundational-decisions. `foundational-decisions.md` D6 validates only cross-listed, EDGAR/US-GAAP companies, which may make SEDAR+ moot for the near term — but that's an inference, not a stated decision. Nothing documents whether the SEDAR+/TSX-only direction was consciously dropped, superseded by D6, or simply deferred and forgotten. Given it's a distinct differentiator direction from the original LedgerLens concept, this deserves an explicit call rather than silent disappearance. (Related: the source's "source reconciliation" strength-to-preserve — reconciling data across multiple filing sources when they conflict — has no counterpart either, likely because it depended on the now-vanished multi-source SEDAR+ direction.)

## Gap 4 — Specific lens sub-metrics named in the source are missing from the PRD's lens FRs

Comparing the source's itemized Quality/Health and Integrity/Evidence lens bullets against `prd.md` §4.2/§4.3:
- **"debt maturity concentration"** (Quality/Health lens) — not mentioned anywhere.
- **"trajectory-over-level rules"** (Quality/Health lens — the principle of weighting improving/worsening trends over static threshold levels) — not mentioned anywhere; the PRD's only "trajectory" language is scoped to the Growth lens (FR-16), not applied to Quality/Health.
- **"receivables versus revenue"** and **"cash versus earnings"** (Integrity/Evidence lens, listed as checks distinct from Beneish/Sloan) — not called out as separate signals anywhere; they may be implicitly folded into Beneish's DSRI or Sloan's accrual calculation, but the source lists them as their own bullets and the PRD doesn't confirm whether they survive as standalone checks or were absorbed.

## Gap 5 — Two Phase 2 deliverables from the four-phase plan have no directional FR

The source's Phase 2 ("Evidence and research experience") list includes "polished company deep dive," "historical trends," and "one or two high-value financial visualizations" as headline items. `prd.md` §4.8–§4.11 translate Phase 2 into FR-14 (Filing Q&A), FR-15 (Value Lens), FR-16 (Growth Lens), and FR-17 (Thesis Journal) — but no FR, even a directional one-liner, covers a company deep-dive/history view or a financial-visualization feature. Compare to how the PRD did preserve other Phase 2 items directionally (peer comparison → FR-12/13, confidence/missing-data indicators → FR-3's "insufficient data" pattern). These two specific items appear to have been dropped rather than deferred-with-a-marker.

## Gap 6 — "Sector heatmap" and "draggable dashboards" (named in source's "Features to defer" list) are missing from the PRD's Non-Goals

The source's explicit "Features to defer" list has ten items. Most reappear explicitly in `prd.md` §5 Non-Goals or §6.2 Out of Scope (full S&P 500 coverage, broad TSX/TSXV, auth/watchlists in initial release, analyze-any-ticker workflows, multiple vector databases, multiple paid providers, subscriptions/payments). Two do not appear anywhere, as either included or explicitly deferred: **sector heatmap** and **draggable dashboards**. Unlike the other deferred items, these are simply absent — silently dropped rather than carried forward as a documented non-goal.

## Note (not a gap, flagged for awareness) — LangGraph adoption reverses a source recommendation

The source's "Features to defer" list explicitly names "GraphRAG or LangGraph" as something to avoid. `foundational-decisions.md` D7 explicitly *adopts* LangGraph for the Phase 2 Filing Q&A/RAG feature, with a reasoned justification (genuine stateful/conditional self-verifying citation loop, tied to the Integrity-lens promise, plus an acknowledged 20%-engineer-showcase motivation). This isn't a silent drop — it's a deliberate, well-argued reversal — but it's worth surfacing explicitly since it's the one place downstream docs knowingly contradict a specific source recommendation rather than just extending or narrowing it.

---

## Not flagged (already adequately covered, confirmed during review)

- The four-phase plan itself, the Value/Growth/Quality/Integrity lens structure, and the core tech-stack choices — all explicitly out of scope per task instructions.
- "Bargain-versus-value-trap framing" — preserved almost verbatim in UJ-1.
- Deterministic/LLM boundary, provenance, accounting-identity validation, graceful degradation via "insufficient data" — all explicitly present (FR-3, FR-7, D-level standing constraints).
- Risk-factor change detection — explicitly addressed via addendum A2's whitespace analysis and folded into Non-Goals with a stated rationale (heavy version non-differentiating, cheap 8-K version preserved as a future add-on).
- Read-only AI copilot boundary — matches PRD's "never investment advice" Non-Goal and FR-11's citation-only explanation rule.
- Immutable raw storage — architecture-level detail, reasonably left for the architecture doc rather than the PRD.
