# Reconciliation: foundational-decisions.md vs. PRD (prd.md + addendum.md)

Date: 2026-07-17
Scope: Verify D1–D7 (locked, `_bmad-output/planning-artifacts/foundational-decisions.md`) are reflected or correctly cross-referenced in `prd.md` / `addendum.md`. Flag only real gaps — silent contradiction, silent omission, or something a PRD-only reader would miss that's load-bearing.

## Decision-by-decision status

### D1 — Product name: ThesisTrace
**Status: GAP (contradiction).** foundational-decisions.md D1 is explicitly "Locked (revisit only via explicit correct-course)." The PRD's own title block (prd.md line 8-9) reads:
```
# PRD: ThesisTrace
*Working title — confirm.*
```
This directly contradicts the locked status. A reader of the PRD alone has no way to know the name was already decided and locked — they'd reasonably conclude it's still open. Should either be removed or reworded to note the name is locked per foundational-decisions.md D1.

### D2 — Primary user
**Status: Covered.** §2 Target User, JTBD list (incl. the "user zero" framing and the explicit ~20%-weighted secondary/contextual JTBD), and §0 Document Purpose all restate this faithfully. No gap.

### D3 — Phase 1 success definition
**Status: Covered, but see Altman gap below.** §7 Success Metrics SM-1 (correctness via golden dataset + regression tests) and SM-2 (real use by user zero) map directly to D3's two conditions. However, SM-1's correctness bar names "Piotroski, Altman, Beneish, and Sloan" — and Altman has no corresponding functional requirement in the PRD (see finding under D5 below), so this metric is currently unfalsifiable/untraceable as written.

### D4 — End-state posture (portfolio-complete, startup-optional)
**Status: Covered by cross-reference.** PRD correctly cites D4 for the no-auth/session-only stance (FR-12, FR-17, Non-Goals §5). The "must not foreclose a future B2C pivot" architectural constraint isn't restated, but that's appropriately architecture-stage detail and the PRD explicitly declines to duplicate foundational-decisions.md. No gap — cross-reference is sufficient per the task's own allowance.

### D5 — Lens sequencing (Phase 1 = Integrity + Quality/Health; Phase 2 = Value + Growth)
**Status: Mostly covered, one significant gap — Altman Z-Score has no functional requirement.**
D5 states Phase 1 includes "Piotroski, Altman, Beneish, Sloan — fully mechanical from XBRL." The PRD's feature sections split these as:
- §4.2 Quality & Health Lens → FR-3/FR-4: Piotroski only.
- §4.3 Integrity & Evidence Lens → FR-5/FR-6/FR-7: Beneish and Sloan only.

Altman Z-Score never gets its own FR for computation, sub-signal display, or provenance (the pattern every other Phase 1 score gets). It only appears as: a glossary example (§3), a parenthetical exclusion note in FR-5's consequences ("excluded from Beneish/Altman computation entirely"), in SM-1's success-metric list, in FR-10's methodology-page list, and in the IFRS Non-Goal. §6.1 MVP Scope (In Scope, Phase 1) likewise never lists an Altman FR. This is a silent omission: a reader relying on the PRD's Features/MVP Scope sections alone would not know Altman is supposed to ship in Phase 1 at all, let alone how — yet SM-1 (the primary success metric) explicitly requires Altman correctness. This is load-bearing and should be flagged/fixed (either add a dedicated FR-3.5-style requirement, or explicitly fold Altman's sub-signals into FR-3/FR-4's scope).

### D6 — Phase 1 company universe (CP, QSR, OTEX, SHOP)
**Status: Covered, one gap — SHOP's flagged thin-history limitation is dropped.**
The universe itself (4 tickers) is faithfully carried into the Glossary, FR-1, UJ-1, and MVP Scope, with correct cross-references to D6 for the financial-sector Beneish/Altman exclusion and IFRS exclusion. However, D6 explicitly and deliberately flags SHOP's 2-year-only 10-K history as "a known Phase 1 limitation... insufficient for longitudinal/Sloan-trend analysis, usable for cross-sectional scoring only." This caveat does not appear anywhere in the PRD — not in FR-6 (Sloan computation), not in SM-1 (which requires "100%... match a hand-verified golden dataset" across the whole universe with no carve-out), not in Non-Goals, not in Open Questions. A reader of the PRD alone would not know SHOP is a weaker case for Sloan/longitudinal analysis, and SM-1 as written sets an expectation (full golden-dataset match for all 4 companies on all 4 scores) that D6 already flagged as potentially unachievable for SHOP's Sloan trend. Worth surfacing explicitly, e.g. as a caveat on FR-6 or an added Open Question.

### D7 — Charting library and LLM orchestration tooling
**Status: Covered.** TradingView exclusion is reflected in §2.2 Non-Users and §5 Non-Goals, both citing D7. LangChain/LangGraph split (no LangGraph for Phase 1 explanation, LangGraph adopted for Phase 2 Q&A) is reflected precisely in FR-11's description and FR-14's description, matching D7's phase split and rationale. Stack inclusions (Next.js/FastAPI/Supabase/pgvector) are referenced appropriately (e.g., "pgvector/RAG infrastructure not yet built" in §6.2, "already-locked Next.js stack" in §5) without needing full restatement — correct use of cross-reference. No gap.

## Summary of real gaps found

1. **D1 contradicted at the top of the PRD** — title block says "Working title — confirm" despite D1 being locked.
2. **D5/D3 — Altman Z-Score has no functional requirement** anywhere in §4 Features or §6.1 MVP Scope, despite being named in D3's success definition, D5's Phase 1 scope, and SM-1's success metric. Significant, load-bearing omission.
3. **D6 — SHOP's flagged thin-history/Sloan-trend limitation is not carried into the PRD** (not in FR-6, not in SM-1's blanket golden-dataset requirement, not in Open Questions), even though D6 explicitly called it out as a known Phase 1 limitation.

D2, D4, D7 are fully and correctly reflected (directly or via appropriate cross-reference).
