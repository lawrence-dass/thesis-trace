# ThesisTrace — Project Handoff

**Purpose of this file:** a single entry point for picking this project back up from a different device or session (e.g. Claude Code mobile/cloud) with zero prior context. Read this first.

## What ThesisTrace is

An evidence-backed equity intelligence platform for retail investors. Four transparent analytical lenses (Value, Growth, Quality/Health, Integrity) computed deterministically from SEC EDGAR filings — never an LLM-invented score. An LLM layer explains already-computed results and answers filing-grounded questions, but never originates a number or gives investment advice. Full product vision: `_bmad-output/planning-artifacts/prds/prd-ThesisTrace-2026-07-17/prd.md`.

Consolidates two prior concepts (LedgerLens + Fundalens); the original comparison lives at `/Users/lawrence/.codex/.chatgpt-projects/g-p-6a582c0cd0608191bbb731d8052a7041/ledgerlens-fundalens-consolidation-review.md` (outside this repo).

## Where things stand (as of 2026-07-21)

| Artifact | Status | Path |
|---|---|---|
| Foundational decisions (D1–D7) | **Locked** | `_bmad-output/planning-artifacts/foundational-decisions.md` |
| PRD | **Final** (3 architecture-surfaced refinements folded in 2026-07-21) | `_bmad-output/planning-artifacts/prds/prd-ThesisTrace-2026-07-17/prd.md` (+ `addendum.md` in the same folder) |
| Architecture spine | **Final** (21 ADs; Reviewer Gate passed 2026-07-21) | `_bmad-output/planning-artifacts/architecture/architecture-ThesisTrace-2026-07-19/ARCHITECTURE-SPINE.md` |
| SPEC kernel | **Final** (14 capabilities; adopts spine + PRD + decisions) | `_bmad-output/specs/spec-thesistrace/SPEC.md` |
| Epics & Stories | **Final** — Phase-1: 4 epics, 26 stories, all 14 FRs covered | `_bmad-output/planning-artifacts/epics.md` |
| Application code | **Epics 1–2 complete** — all four models live (Piotroski, Altman+Tiingo, Beneish, Sloan) with sub-signal displays, provenance, data-quality flags; 43 backend tests green. Next: Epic 3 (Verdict/Methodology/Explanation) | `backend/`, `frontend/`, `db/` |
| Git repo / GitHub | **Initialized** (`lawrence-dass/thesis-trace`); work branch `claude/codebase-review-setup-rz93qm` | — |

## Architecture spine — finalized 2026-07-21

The spine is **final** (`status: final`), now **21 ADs**. The paused Finalize sequence was completed in a Claude cloud session:

- **Reviewer Gate passed.** `lint_spine.py` clean (0 findings). Three lenses ran as parallel subagents against the spine — rubric walker, web/version verification, and adversarial two-units-diverge — with full reviews saved under `.../architecture-ThesisTrace-2026-07-19/reviews/`.
- **Fixes applied from the gate:** six new invariants (AD-16 tri-state signal status; AD-17 single `data_quality_issues` contract/owner; AD-18 canonical `score_results` shape + `signal_key` vocabulary; AD-19 provenance as a first-class invariant; AD-20 sector-scope applicability state; AD-21 FR-12 LLM = Claude Haiku default, env-keyed, out of the numeric loop). Tightened AD-4 (dual-source tiebreaker), AD-5/AD-15 (one shared rounding engine), AD-6 (current-run selection), AD-8/AD-12 (band classification computed backend), AD-14 (FYE trading-day price). Refreshed stale Python version pins (FastAPI 0.139, Pydantic 2.13, SQLAlchemy 2.0.51 — Next.js 16.2.10 / React 19.2.7 re-verified current). Fixed a mermaid diagram bug (frontend was under Render, belongs on Vercel).
- **Two product calls confirmed by Lawrence:** Piotroski Verdict bands corrected to the paper's own classification (Strong 8-9, Weak 0-1, 2-7 = Middle/mixed — the prior 5-7/0-4 split was invented); FR-12 LLM pinned to Claude Haiku 4.5.

Full run memory: `.../architecture-ThesisTrace-2026-07-19/.memlog.md` (44 entries).

## Standing decisions a future session must respect

These are locked/final and shouldn't be silently re-litigated — see the source docs for full reasoning:

- **Deterministic/LLM boundary (inviolable):** all scores/numbers computed deterministically; LLM only explains + cites, never originates a figure or gives advice.
- **Phase 1 company universe:** CP, QSR, OTEX, SHOP — validated live against EDGAR (cross-listed Canadian, US-GAAP 10-K filers, non-financial sector).
- **Phase 1 scope:** all four deterministic models (Piotroski, Altman, Beneish, Sloan) — Altman's market-value-of-equity term uses Tiingo (free tier) for closing price, joined with EDGAR's own `dei:EntityCommonStockSharesOutstanding`. Value + Growth lenses (DCF, growth trajectory, etc.) are Phase 2.
- **Verdict:** shown as a transparent per-model threshold classification, never a blended/weighted single score.
- **No TradingView / off-the-shelf charting** — custom visualizations only (differentiates from Lawrence's sibling portfolio project `equipulse`).
- **LangGraph** reserved for Phase 2 Filing Q&A only — Phase 1's explanation feature is a plain direct LLM wrapper, never LangGraph.
- **No end-user auth in Phase 1** — public, read-only. Notifications (Phase 3) use email-only capture, no accounts.
- **Cost ceiling:** ~$25/month total (hosting + data + LLM). Current architecture: Render (~$8-10/mo) + Vercel (free) + Supabase (free) + Tiingo (free) — leaves ample headroom for LLM costs.
- **Web-only** — no native mobile app is planned for the *product itself* (unrelated to Lawrence developing *from* a mobile/cloud session).

Three PRD-touching refinements surfaced during architecture work and have now been **folded back into `prd.md`** (2026-07-21):
- FR-12 (AI explanation) tightened to "deterministic template first, LLM as constrained rewrite only," Claude Haiku default (spine AD-7/AD-21). ✅
- FR-9 (Verdict) now states the per-model-threshold-juxtaposition synthesis rule with paper-faithful Piotroski bands and backend-computed labels (spine AD-8/AD-12). ✅
- FR-4 (Altman) now notes the Tiingo market-data dependency (spine AD-11/AD-14). ✅
- Also: PRD Open Question 2 (restatement policy) marked resolved by spine AD-6. ✅

## What's left before development starts

Planning is now complete end-to-end (PRD → foundational decisions → architecture spine → SPEC → epics & stories). Development can begin.

1. **`bmad-create-story`** — draft the first implementable story, **Epic 1 Story 1.1 (project scaffold & deployable skeleton)**, with full dev context, then implement it. This is the recommended next step.
2. Proceed through Epic 1 in order (1.1 → 1.10) — it is the walking skeleton (Shopify-first, Piotroski + Sloan, EDGAR-only) that proves the whole pipeline.
3. Or invoke **`bmad-help`** for authoritative routing if priorities shift.

The story backlog lives in `_bmad-output/planning-artifacts/epics.md` (4 epics, 26 stories). Each story cites the FR/AD it fulfills.

Environment note for cloud/web sessions: once the first code lands (Story 1.1), add a `README`, a `.claude/` SessionStart hook, and `.env.example` (EDGAR contact, Tiingo key, LLM key, DB URL) so a fresh web container can `install`/`test`/run immediately. Story 1.1's acceptance criteria already include `.env.example` and a health check.

## Everything on disk right now

```text
ThesisTrace/
  HANDOFF.md                                    # this file
  _bmad-output/planning-artifacts/
    foundational-decisions.md                   # D1-D7, locked
    prds/prd-ThesisTrace-2026-07-17/
      prd.md                                    # final (refinements folded 2026-07-21)
      addendum.md                                # competitor/whitespace research depth
      .memlog.md                                 # full PRD-run decision trail
      review-rubric.md, reconcile-*.md           # PRD review/reconciliation artifacts
    architecture/architecture-ThesisTrace-2026-07-19/
      ARCHITECTURE-SPINE.md                      # FINAL — 21 ADs
      .memlog.md                                 # full architecture-run decision trail (44 entries)
      reconcile-prd.md                           # reconciliation findings (AD-11/D7 issue)
      reviews/                                   # Reviewer Gate output (3 lens reviews)
```
