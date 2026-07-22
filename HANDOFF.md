# ThesisTrace — Project Handoff

**Purpose of this file:** a single entry point for picking this project back up from a different device or session (e.g. Claude Code mobile/cloud) with zero prior context. Read this first.

## What ThesisTrace is

An evidence-backed equity intelligence platform for retail investors. Four transparent analytical lenses (Value, Growth, Quality/Health, Integrity) computed deterministically from SEC EDGAR filings — never an LLM-invented score. An LLM layer explains already-computed results and answers filing-grounded questions, but never originates a number or gives investment advice. Full product vision: `_bmad-output/planning-artifacts/prds/prd-ThesisTrace-2026-07-17/prd.md`.

Consolidates two prior concepts (LedgerLens + Fundalens); the original comparison is now in-repo at `_bmad-output/planning-artifacts/ledgerlens-fundalens-consolidation-review.md` (copied 2026-07-20 from its original location outside version control, so cloud/mobile sessions can read it).

## Where things stand (as of 2026-07-21)

| Artifact | Status | Path |
|---|---|---|
| Foundational decisions (D1–D7) | **Locked** | `_bmad-output/planning-artifacts/foundational-decisions.md` |
| PRD | **Final** (3 architecture-surfaced refinements folded in 2026-07-21) | `_bmad-output/planning-artifacts/prds/prd-ThesisTrace-2026-07-17/prd.md` (+ `addendum.md` in the same folder) |
| Architecture spine | **Final** (21 ADs; Reviewer Gate passed 2026-07-21) | `_bmad-output/planning-artifacts/architecture/architecture-ThesisTrace-2026-07-19/ARCHITECTURE-SPINE.md` |
| SPEC kernel | **Final** (14 capabilities; adopts spine + PRD + decisions) | `_bmad-output/specs/spec-thesistrace/SPEC.md` |
| Epics & Stories | **Final** — Phase-1: 4 epics, 26 stories, all 14 FRs covered | `_bmad-output/planning-artifacts/epics.md` |
| Application code | **Epics 1–4 complete (Phase 1)** — all four models live (Piotroski, Altman+Tiingo, Beneish, Sloan), Verdict/Methodology/Explanation, Discovery & Comparison. 48 backend tests green (see 2026-07-21 fix below — was 43). Merged to `main` via PR #1. | `backend/`, `frontend/`, `db/` |
| Git repo / GitHub | **Initialized** (`lawrence-dass/thesis-trace`), Phase 1 merged to `main` | — |

## Architecture spine — finalized 2026-07-21

The spine is **final** (`status: final`), now **21 ADs**. The paused Finalize sequence was completed in a Claude cloud session:

- **Reviewer Gate passed.** `lint_spine.py` clean (0 findings). Three lenses ran as parallel subagents against the spine — rubric walker, web/version verification, and adversarial two-units-diverge — with full reviews saved under `.../architecture-ThesisTrace-2026-07-19/reviews/`.
- **Fixes applied from the gate:** six new invariants (AD-16 tri-state signal status; AD-17 single `data_quality_issues` contract/owner; AD-18 canonical `score_results` shape + `signal_key` vocabulary; AD-19 provenance as a first-class invariant; AD-20 sector-scope applicability state; AD-21 FR-12 LLM = Claude Haiku default, env-keyed, out of the numeric loop). Tightened AD-4 (dual-source tiebreaker), AD-5/AD-15 (one shared rounding engine), AD-6 (current-run selection), AD-8/AD-12 (band classification computed backend), AD-14 (FYE trading-day price). Refreshed stale Python version pins (FastAPI 0.139, Pydantic 2.13, SQLAlchemy 2.0.51 — Next.js 16.2.10 / React 19.2.7 re-verified current). Fixed a mermaid diagram bug (frontend was under Render, belongs on Vercel).
- **Two product calls confirmed by Lawrence:** Piotroski Verdict bands corrected to the paper's own classification (Strong 8-9, Weak 0-1, 2-7 = Middle/mixed — the prior 5-7/0-4 split was invented); FR-12 LLM pinned to Claude Haiku 4.5.

Full run memory: `.../architecture-ThesisTrace-2026-07-19/.memlog.md` (44 entries).

## Real bug found and fixed post-implementation (2026-07-21)

A desktop session independently ran the architecture spine's Reviewer Gate a second time (parallel to the cloud session's own work — see "Note on parallel sessions" below) and its adversarial + web-verification lenses converged on a genuine, live-verified correctness bug that had made it into shipped code:

**The bug:** `backend/canonicalization/mappings.py` mapped `shares_outstanding` from `dei:EntityCommonStockSharesOutstanding` — a 10-K cover-page fact dated to the *filing* date, not fiscal year-end. Confirmed live against SEC EDGAR (CP, QSR, OTEX): for a December-FYE filer that files in Jan/Feb, this fact's `end` date falls in the *next calendar year*. Since canonicalization groups raw facts by `period_end.year`, this silently misfiled `shares_outstanding` under the wrong fiscal year for essentially every real company — meaning **Altman's X4 term and Piotroski's `shares_not_diluted` signal would have shown `insufficient_data` for real production filings**, not the small date-approximation issue the original AD-11 language implied. The shipped test suite didn't catch it because its fixture used unrealistic dates (dei `end` = FYE exactly, which real EDGAR data never does).

**The fix:** `shares_outstanding` now resolves through a priority-ordered concept fallback: `us-gaap:CommonStockSharesOutstanding` (confirmed genuinely FYE-dated for single-class filers CP/QSR/OTEX) first, `us-gaap:WeightedAverageNumberOfSharesOutstandingBasic` (confirmed FYE-dated, needed for SHOP's multi-class share structure, whose 10-Ks don't tag the point-in-time concept at all) as fallback. `canonicalize.py`'s selection ranking gained a concept-priority tier (using the `ConceptMapping.priority` field, which existed in the schema but was never consulted). `MAPPING_VERSION` bumped `concepts_v1` → `concepts_v2` per AD-2. Added a regression test (`test_shares_outstanding_prefers_point_in_time_over_dei_and_ignores_wrong_year_dei`) — verified it fails against the original code and passes against the fix, by literally reverting and re-running. All 48 backend tests pass (verified against a real Postgres 17 container, not just reasoning).

**Note on parallel sessions:** while this fix was being worked out, the desktop's local git history had diverged from `origin/main` (the cloud session had raced ahead through spec → epics → full Phase 1 implementation while the desktop session was still running its own copy of the architecture Reviewer Gate). The desktop's redundant spine-only changes were discarded (`git reset --hard origin/main`) in favor of the cloud session's already-implemented code; only this real bug fix was carried forward as a new commit on top of the merged Phase 1 work.

### Why this happened, and the fix (2026-07-21)

Root cause: two sessions were mutating the *same shared, stateful planning artifacts* (the architecture spine and its memlog) with no signal to each other that the other was active. BMad's "resume from memlog" design assumes serial handoffs, not concurrent sessions — it has no lock or in-progress marker. Git only caught the collision at push time, after both sessions had already done substantial independent work, making the divergence large and effortful to reconcile instead of small and obvious. One asymmetry made it worse: the cloud session worked on a feature branch and merged via PR (the safer pattern); the desktop session was pushing straight to `main`, so the collision surfaced as a raw rejected push rather than a normal, expected PR conflict.

**The fix, going forward — see `CLAUDE.md`'s "Git workflow" section (binding, read every session):** every session, cloud or desktop, works on its own new feature branch and merges back via PR — never a direct push to `main`. This doesn't prevent two sessions from working concurrently (that's fine, and the redundant review in this exact incident caught a real bug), it just makes any real conflict surface as an ordinary, reviewable PR diff instead of a git-history divergence discovered after the fact.

## Standing decisions a future session must respect

These are locked/final and shouldn't be silently re-litigated — see the source docs for full reasoning:

- **Deterministic/LLM boundary (inviolable):** all scores/numbers computed deterministically; LLM only explains + cites, never originates a figure or gives advice.
- **Phase 1 company universe:** CP, QSR, OTEX, SHOP — validated live against EDGAR (cross-listed Canadian, US-GAAP 10-K filers, non-financial sector).
- **Phase 1 scope:** all four deterministic models (Piotroski, Altman, Beneish, Sloan) — Altman's market-value-of-equity term uses Tiingo (free tier) for closing price, joined with shares outstanding from a priority-ordered EDGAR concept chain (`us-gaap:CommonStockSharesOutstanding` primary, `us-gaap:WeightedAverageNumberOfSharesOutstandingBasic` fallback for multi-class filers like SHOP) — **not** `dei:EntityCommonStockSharesOutstanding`, which is filing-date-dated, not FYE, and was found and fixed as a real bug 2026-07-21 (see below). Value + Growth lenses (DCF, growth trajectory, etc.) are Phase 2.
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

## How Lawrence works (for any AI session picking this up)

This isn't captured anywhere else in the repo — it's local assistant memory on the desktop machine, which a cloud/mobile session won't have access to:

- **Wants research-backed grounding, not assertions.** Before a feature, competitor-differentiation claim, or technical assumption gets locked in, verify it (live data checks, web research, named comparables) rather than reasoning from training data alone. He explicitly invites this ("you can do research if needed") and expects it even when he doesn't ask.
- **Quality over reduced scope.** When a real technical gap surfaces (e.g., Altman's market-data dependency), don't default to the option that cuts scope or defers the hard part just because it's offered as "the pragmatic choice." He's willing to invest more engineering effort to keep a feature fully correct rather than simplify it away. Solve the underlying problem; reserve simplification for when the simpler path is *also* the higher-quality one.
- **Catches gaps himself and expects them taken seriously.** His "wait, did we cover X?" questions (e.g. the missing multi-ticker comparison feature, the Altman data question) are genuine gap-finding, not idle curiosity — verify before answering rather than reassuring from memory.
- **Values honest pushback.** He responded well to direct pushback like "wrapping a trivial LLM call in LangGraph would read as keyword-stuffing to a technical reviewer" — don't just validate every idea.

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
