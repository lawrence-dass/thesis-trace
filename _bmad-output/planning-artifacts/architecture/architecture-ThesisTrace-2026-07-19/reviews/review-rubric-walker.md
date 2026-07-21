# Architecture Spine Review — ThesisTrace

**Reviewer:** rubric-walker (good-spine checklist)
**Target:** `_bmad-output/planning-artifacts/architecture/architecture-ThesisTrace-2026-07-19/ARCHITECTURE-SPINE.md`
**Sources consulted:** `prd.md` (FR-1..FR-21, SM-1..SM-4), `foundational-decisions.md` (D1..D7)
**Date:** 2026-07-21

---

## Verdict: pass-with-fixes

This is a strong, unusually disciplined spine. The write/read (CQRS) split, immutability/versioning invariants, the deterministic-vs-LLM boundary, and the operational envelope are all decided or explicitly deferred with justification — no whole dimension is silently dropped, and the operational/environmental envelope (checklist item 7) is genuinely covered (Render/Vercel/Supabase, single-prod-plus-local, monitoring deferred to Phase 4 on purpose). All 21 FRs are mapped (item 6), and Phase 2/3 FRs are deferred consistently with the PRD phasing.

It falls short of a clean pass because a few real Phase-1 divergence points are not pinned as invariants (sector-scope applicability, the provenance contract, missing-input state), the LLM provider/model and the golden-dataset/test strategy are silent despite both being Phase-1 and initiative-owned, one internal contradiction exists (frontend hosting), one AD silently modifies an FR without a tracked open question, and several pinned versions are stale or non-existent. None are structural; all are fixable in place.

---

## Findings

### HIGH

**H1 — Sector-scope applicability is a real divergence point and has no invariant (checklist item 1).**
Location: whole spine; relates to AD-3, AD-11, AD-12, FR-4, FR-6.
FR-4 and FR-6 (and D6) require that financial-sector firms be *excluded entirely* from Altman/Beneish, while capital-intensive firms (e.g., ENB) carry an *interpretive caveat* rather than a bare number. This is exactly the kind of rule two independently-built units will diverge on: the scoring module may skip computation, while the read API / frontend may still render a slot, or invent its own "N/A" representation. Nothing in the spine states where model-applicability is decided, how "excluded" vs "caveated" is represented in `score_results`, or that the read path must render the model's own applicability state rather than a default. 
Suggested fix: add an AD (e.g., AD-16 "Model applicability is a first-class, persisted score state") establishing that each `score_run`/`score_result` records an explicit applicability status (`computed` / `excluded_out_of_scope` / `computed_with_caveat`) with a machine-readable reason, and that the read path renders that status verbatim — never a bare number and never a silently omitted slot.

**H2 — The Provenance contract, the product's core promise, is not pinned as an invariant (item 1).**
Location: Structural Seed ER diagram; AD-2; Capability map FR-5/FR-8.
"Every conclusion traceable back to the actual filing line item" is the differentiator (PRD §1, glossary "Provenance", FR-5/FR-8 "each value links to its Provenance record"). Yet no AD defines the provenance link shape (canonical_fact -> filing + specific XBRL concept + accession/context), and the ER diagram has no explicit provenance/citation attribute — it must be reconstructed through `concept_mappings`. Backend (what it emits) and frontend (what it renders) will diverge on the citation payload without a fixed contract. This also underpins AD-7's guarantee that the LLM cites only existing provenance.
Suggested fix: add an AD fixing the provenance record as a stable, API-exposed shape (source filing `accession_number`, XBRL concept/tag, context/period, value, `fetched_at`), asserting every `canonical_fact` and every displayed score sub-signal resolves to exactly one provenance record, and that the read API returns it inline with each value.

### MEDIUM

**M1 — LLM provider/model is silent despite being a Phase-1, initiative-owned dimension (item 7).**
Location: Stack table; AD-7; Consistency Conventions ("LLM key" env var).
FR-12 (cited narrative explanation) ships in Phase 1 and uses an LLM; the resolved cost ceiling (~$25/mo, PRD OQ4) explicitly budgets LLM spend. The Stack table names no LLM provider or model, and there is no AD or open question capturing the choice. A model/provider decision that materially affects cost and behavior is left entirely unstated.
Suggested fix: either add the chosen LLM provider+model (and rough token/cost envelope) to the Stack table, or record it as an explicit Open Question if not yet decided — do not leave it silent.

**M2 — Golden-dataset / test strategy is silent though it is the #1 success metric (item 7).**
Location: whole spine; SM-1; AD-15; PRD Open Question 1.
SM-1 (100% golden-dataset match, enforced by regression tests) is the primary quality bar and the whole reason AD-15 (NUMERIC-only) exists. PRD OQ1 (golden-dataset sourcing) is unresolved and flagged as *blocking SM-1 measurement*. The spine addresses numeric fidelity but never states where golden datasets live, how regression tests bind to `formula_version` (AD-5), or that a score is not "done" until it matches golden. For an initiative whose success is defined by correctness, verification is a dimension that should be decided/deferred, not omitted.
Suggested fix: add a brief "Verification" invariant (golden datasets are versioned artifacts keyed to `formula_version`; every Phase-1 score has a golden fixture; regression is the gate for SM-1) and surface PRD OQ1 in an Open Questions section rather than leaving it out of the spine.

**M3 — Internal contradiction: frontend hosting is both Render and Vercel (item 2 / consistency).**
Location: Invariants mermaid diagram (Read subgraph labeled "Render Web Service" containing `WEB[Next.js frontend]`) vs. Stack table + Deployment section (Vercel free/hobby for Next.js).
The diagram groups the Next.js frontend under "Render Web Service," while the Stack table and Deployment paragraph place it on Vercel. A builder wiring deployment could pick either. 
Suggested fix: correct the diagram's Read subgraph so the Next.js frontend sits on Vercel and only the FastAPI read API sits on the Render Web Service; keep AD-13 scoped to the backend.

**M4 — AD-7 modifies FR-12 "pending PM confirmation" but no tracked open question exists (item 2 / item 6).**
Location: AD-7 ("Tightens FR-12 beyond the PRD's 'cited narrative' language; flagged as a PRD-touching refinement pending PM confirmation").
AD-7 narrows FR-12 from "LLM generates cited narrative" to "template-generated text; LLM may only rewrite already-correct text." This is a defensible tightening and consistent with D5/D7's inviolable boundary, but it silently diverges from the FR it binds, and the "pending PM confirmation" is a dangling dependency with no home — the spine has no Open Questions section.
Suggested fix: add an Open Questions section (or a "PRD-touching refinements" note) that names this as an item requiring PM sign-off, so it cannot be lost. Confirm whether FR-12's "plain-language explanation… the LLM receives only already-computed facts" is fully satisfied by template + constrained rewrite.

**M5 — Named tech is partly stale or non-existent (item 4).**
Location: Stack table.
Verified against current releases (July 2026):
- **Next.js 16.2.10** — the latest published stable is **16.2.7** (June 2026). 16.2.10 does not exist; this is an ahead-of-reality/fabricated patch. Pin to 16.2.x (current 16.2.7) or drop the false-precision patch.
- **Pydantic 2.10.x** — stale by ~18 months; current line is **2.12/2.13**. Bump to 2.12.x.
- **SQLAlchemy 2.0.36** — current is **2.0.51**. Same 2.0.x stable line, but the pinned patch is ~15 releases behind; bump.
- **FastAPI 0.136.x** — current is **0.139.2**; 0.136 is slightly behind but exists (minor).
- **Postgres 17** — fine/conservative (PG18 exists but 17 is fully supported). **React 19.2** line and **Python 3.12/3.13** are fine.
Suggested fix: refresh Next.js, Pydantic, and SQLAlchemy pins to current; avoid patch-level precision on Next.js unless intentionally locked.

### LOW

**L1 — "Insufficient data" (missing input) is not pinned as a shared state, distinct from AD-3 ambiguity (item 1).**
Location: AD-3; FR-3/FR-16/FR-17 "insufficient data" pattern.
AD-3 covers *ambiguous/conflicting* facts (-> `data_quality_issues` `needs_review`). But FR-3 (and the Phase-2 FRs that inherit its pattern) require that a *missing* required fact marks the affected signal "insufficient data" rather than defaulting. Missing-input handling is a distinct state; independently-built score modules could represent it inconsistently (null, 0, skip, flag).
Suggested fix: extend AD-3 (or add a short rule) that a missing required input yields an explicit, persisted per-signal "insufficient_data" state — never a default, guess, or silent zero — shared across all score modules.

**L2 — Live-vs-pending lens representation not pinned (item 1).**
Location: AD-12; FR-9, FR-14.
FR-9 and FR-14 both require the UI to state which lenses are *live vs. pending* for the current phase. AD-12 fixes verdict synthesis but not the live/pending status contract that both the overview and comparison views consume. Minor divergence risk between the two views.
Suggested fix: note in AD-12 (or the Capability map) that lens liveness is a phase-driven status the read API emits and both views render identically.

**L3 — Deferred "exact accounting-identity validation rule set" is a Phase-1 capability (FR-8) left behaviorally undefined (item 3).**
Location: Deferred list; FR-8.
This is not a two-units-diverge risk (one validation module owns `data_quality_issues`), so deferral is acceptable — but FR-8 is in-scope Phase 1, so the *presence* of at least a minimal balance-check should be affirmed rather than reading as fully punted.
Suggested fix: state that the mechanism and at least the FR-8 balance-sheet-balances check are Phase 1; only the broader rule set is deferred.

---

## Checklist scorecard

1. Fixes real divergence points, misses none — **partial** (misses sector applicability H1, provenance H2, missing-input state L1, lens-liveness L2).
2. Every AD's rule enforceable / prevents its divergence — **mostly yes**; AD-7 modifies its FR untracked (M4); one internal contradiction (M3).
3. Nothing under Deferred lets units diverge — **yes** (L3 is a behavioral-completeness nit, not a divergence risk; Sloan threshold and identity checks each live in one owning module).
4. Named tech verified-current — **no** (M5: Next.js version non-existent, Pydantic/SQLAlchemy stale).
5. Ratifies brownfield codebase — **N/A** (greenfield).
6. Covers spec capabilities FR-1..FR-21 — **yes**; caveat M4 (FR-12 tightened) and the sector/provenance gaps above affect fidelity, not coverage.
7. Every initiative-altitude dimension decided/deferred/open, esp. operational envelope — **mostly yes**; operational/environmental envelope well handled; gaps are LLM provider (M1) and verification/golden-dataset strategy (M2).
