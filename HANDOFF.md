# ThesisTrace — Project Handoff

**Purpose of this file:** a single entry point for picking this project back up from a different device or session (e.g. Claude Code mobile/cloud) with zero prior context. Read this first.

## What ThesisTrace is

An evidence-backed equity intelligence platform for retail investors. Four transparent analytical lenses (Value, Growth, Quality/Health, Integrity) computed deterministically from SEC EDGAR filings — never an LLM-invented score. An LLM layer explains already-computed results and answers filing-grounded questions, but never originates a number or gives investment advice. Full product vision: `_bmad-output/planning-artifacts/prds/prd-ThesisTrace-2026-07-17/prd.md`.

Consolidates two prior concepts (LedgerLens + Fundalens); the original comparison is now in-repo at `_bmad-output/planning-artifacts/ledgerlens-fundalens-consolidation-review.md` (copied 2026-07-20 from its original location outside version control, so cloud/mobile sessions can read it).

## 🔵 Session note (2026-07-22, cloud): environment constraint on the golden-dataset investigation

A cloud session tried to resume the golden-dataset investigation (below) per this file's exact resume steps and hit a hard environment blocker: this particular sandbox had no Docker daemon (no local Postgres), no `.env`/`TIINGO_API_KEY`, and outbound network access to `data.sec.gov` was rejected by the sandbox's own network policy (403 on CONNECT — a deliberate policy denial, not a fixable client-side config issue). None of the resume steps (DB queries, live EDGAR tag verification, pipeline runs) were executable there. Rather than fabricate verification results or add unverified concept fallbacks to `mappings.py` (exactly the class of mistake that caused the shares_outstanding bug), the session deferred that work and instead shipped the not-investment-advice disclaimer (PRD Open Question 3, see "What's left" below) — a self-contained frontend change needing no DB or network access.

**Implication for whoever picks up the golden-dataset investigation next:** confirm your session/environment actually has Docker + Postgres + outbound network access to `data.sec.gov` and Tiingo before starting — a cloud session isn't guaranteed to have these depending on how its environment/network policy was configured. If unsure, check early (e.g. `docker ps`, a `curl` to `data.sec.gov`) rather than discovering the blocker mid-investigation.

## Where things stand (as of 2026-07-22)

| Artifact | Status | Path |
|---|---|---|
| Foundational decisions (D1–D7) | **Locked** | `_bmad-output/planning-artifacts/foundational-decisions.md` |
| PRD | **Final** (refinements folded 2026-07-21) | `_bmad-output/planning-artifacts/prds/prd-ThesisTrace-2026-07-17/prd.md` (+ `addendum.md` in the same folder) |
| Architecture spine | **Final** (21 ADs; Reviewer Gate passed 2026-07-21) | `_bmad-output/planning-artifacts/architecture/architecture-ThesisTrace-2026-07-19/ARCHITECTURE-SPINE.md` |
| SPEC kernel | **Final** (14 capabilities; adopts spine + PRD + decisions) | `_bmad-output/specs/spec-thesistrace/SPEC.md` |
| Epics & Stories | **Final** — Phase-1: 4 epics, 26 stories, all 14 FRs covered | `_bmad-output/planning-artifacts/epics.md` |
| Sprint status | Generated 2026-07-21 — all 4 Phase-1 epics / 26 stories marked `done` | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| Application code | **Epics 1–4 implemented** — all four models, Verdict/Methodology/Explanation, Discovery & Comparison. Verified against **real** EDGAR + Tiingo data for all 4 companies (2026-07-21), not just fixtures. 48 backend tests green. | `backend/`, `frontend/`, `db/` |
| Frontend design system | **Done 2026-07-21** — Tailwind v4 + semantic tokens (tri-state signal palette), reusable UI primitives, all 4 pages restyled. Lawrence confirmed it looks good. | `frontend/app/globals.css`, `frontend/app/components/ui/` |
| Deployment | **Not done — local only.** Everything so far runs against a local Docker Postgres + local `uvicorn`/`next dev`. `render.yaml` exists but nothing has actually been pushed to Render/Vercel/a real Supabase project yet. | — |
| Golden-dataset verification (SM-1 / PRD OQ1) | **IN PROGRESS, paused 2026-07-22 mid-investigation** — see the section below, read it before doing anything else. | `backend/tests/golden/phase1_golden.yaml` |
| Git repo / GitHub | **Initialized** (`lawrence-dass/thesis-trace`), Phase 1 + design system merged to `main` via PRs #1–#6. Branch-per-session + PR workflow is now binding — see `CLAUDE.md`. | — |

## 🔴 IN PROGRESS: Golden-dataset verification (started 2026-07-22, paused mid-investigation)

Lawrence chose this as the next priority over deploying or starting Phase 2: **PRD Open Question 1 / success metric SM-1** ("100% of scores match a hand-verified or published golden dataset") is still unresolved. The existing `backend/tests/golden/phase1_golden.yaml` file's header literally says **"⚠️ PLACEHOLDER VALUES — NOT YET AUTHORITATIVE"** — even Shopify's "golden" values are just characterization values computed from a synthetic fixture, not real hand-verified figures. CP/QSR/OTEX have zero golden coverage (`status: pending_fixture`).

**Investigation so far found real bugs — do not skip straight to sourcing golden values, fix these first:**

1. **Beneish M-Score never computes a value for ANY company/year, ever.** Queried the local dev DB (populated with real EDGAR data — `SELECT * FROM score_runs WHERE aggregate_value IS NOT NULL` across CP/QSR/OTEX/SHOP, all years) — zero Beneish rows. Root cause: three of Beneish's required canonical concepts (`cogs`, `sga`, `long_term_debt`) **never resolve to a value for any of the 4 companies** — `canonical_facts` has zero rows for these concepts. Beneish needs all 8 indices present to produce an aggregate, so it always short-circuits to `insufficient_data`.
   - Confirmed live against real EDGAR company-facts (2026-07-22): the current mapping (`backend/canonicalization/mappings.py`) uses `us-gaap:CostOfRevenue`, `us-gaap:SellingGeneralAndAdministrativeExpense`, `us-gaap:LongTermDebtNoncurrent` — none of which most of these companies actually tag.
   - **Verified alternate tags exist and should be added as priority-ordered fallbacks** (same pattern already used for `shares_outstanding` — see the bug fix further down this file):
     - `cogs`: SHOP and QSR have `us-gaap:CostOfGoodsAndServicesSold`; OTEX already has `CostOfRevenue` (fine); **CP has neither tag at all** — plausibly a genuine data-availability gap (CP is a railroad; railroads typically don't report a single COGS line, using functional expense categories instead), not a bug — needs confirming against an actual CP 10-K before accepting as permanent `insufficient_data`.
     - `sga`: QSR already has `SellingGeneralAndAdministrativeExpense` (fine); SHOP and OTEX have `us-gaap:GeneralAndAdministrativeExpense` instead; **CP has neither** — same railroad caveat as above.
     - `long_term_debt`: QSR and OTEX have `us-gaap:LongTermDebtNoncurrent` (fine); **SHOP and CP have neither `LongTermDebtNoncurrent` nor `LongTermDebt`.** For SHOP this may genuinely mean near-zero long-term debt (asset-light company) rather than a missing tag. For CP, a broader search turned up `us-gaap:LongTermDebtAndCapitalLeaseObligations` (and Noncurrent/Current variants) as a plausible real tag — **not yet verified for exact year coverage**, this is the next concrete step.
   - Also found: **CP is missing `revenue` and `net_income` canonical facts for fiscal years 2014–2021** (has them for 2013, 2022–2025 only), even though `total_assets`/`current_assets`/`cash_from_operations` exist for every one of those years — meaning Piotroski scores for CP's early years (currently sitting at suspiciously low 1–3 out of 9) are likely artificially depressed by missing inputs, not genuine weak fundamentals. Confirmed live: CP's `us-gaap:Revenues` tag exists but doesn't cover 2014–2021 the way the current single-tag mapping assumes; CP also has both `us-gaap:NetIncomeLoss` **and** `us-gaap:ProfitLoss` tags — the latter is currently unmapped and is the likely fix for the missing years (needs exact per-year verification, not yet done).

2. **SHOP's Altman Z-Score never resolves to a non-null aggregate**, despite the pipeline log reporting `altman: [2024, 2025]` as "scored" for Shopify. The DB query for non-null `aggregate_value` rows shows zero Altman rows for SHOP at all (CP and QSR do have real non-null Altman values). **Not yet diagnosed** — likely one of Altman's 5 inputs (`current_assets`, `current_liabilities`, `total_assets`, `retained_earnings`, `ebit`, `total_liabilities`, `revenue`, or the Tiingo-sourced market value of equity) is missing or `None` for SHOP specifically for those years. Check each canonical concept's coverage for SHOP the same way the Beneish diagnosis above was done (`SELECT DISTINCT fiscal_year FROM canonical_facts WHERE issuer_cik = '0001594805' AND canonical_concept = '<concept>'` for each of Altman's inputs), find which one is empty/missing for 2024–2025, then decide whether it's a mapping gap (fixable) or a genuine data limitation.

**Exact resume steps, in order:**
1. Finish diagnosing the SHOP Altman null issue (above).
2. Verify the candidate fallback tags' exact per-year coverage (especially CP's `ProfitLoss`, `LongTermDebtAndCapitalLeaseObligations` variants) against live EDGAR data before committing to them — don't assume a tag's mere *existence* means it covers the *right years*, that assumption bit us before (the whole `shares_outstanding` bug was exactly this class of mistake).
3. Add the verified fallbacks to `MAPPING_RULES` in `backend/canonicalization/mappings.py` using the existing priority-ordered pattern (see `shares_outstanding`'s two-tier example already in that file), bump `MAPPING_VERSION` per AD-2.
4. Re-run canonicalization + scoring (`uv run --env-file ../.env python3 -m pipeline.run` from `backend/`, after `uv run --project backend --env-file .env alembic upgrade head` if any schema changed) and confirm Beneish now produces real values and CP's early-year Piotroski scores look more plausible.
5. **Only then** do the actual golden-dataset sourcing/hand-verification work: pick one fiscal year per company (ideally the most recent year where all 4 models compute a non-null aggregate), independently derive the expected Piotroski/Altman/Beneish/Sloan values by hand directly from the real 10-K figures (cross-check against, but do not simply copy, what the pipeline itself computed — that would just be circular), and only accept a match as "golden" if the independent hand-calculation and the pipeline's output genuinely agree.
6. Replace the placeholder `phase1_golden.yaml` with real values, add real (not synthetic) EDGAR-derived fixtures for CP/QSR/OTEX alongside SHOP's, flip `status: pending_fixture` → `active` for all three, and extend `test_golden_dataset.py` accordingly.
7. This closes PRD Open Question 1 and lets SM-1 actually be claimed as met, rather than assumed.

No code has been changed yet for this investigation — it's been read-only diagnosis (DB queries + live EDGAR checks) against the existing, unmodified `main` branch. Whoever picks this up should start a fresh branch per `CLAUDE.md`'s workflow rule before making any changes.

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

## Real data wired up, more bugs found and fixed (2026-07-21)

Before the golden-dataset work above, the pipeline was run live for the first time (see PR #5's commit message for full detail — this is a summary): CP/QSR/OTEX had never actually had their CIKs wired into `pipeline/universe.py` (only SHOP ever ran), and `pipeline/run.py`'s live entry point never called Tiingo at all, so Altman could never compute for anyone. Fixing both surfaced two more real bugs, now fixed: (1) `score_runs.accession_number` was derived from `Filing.fiscal_year` — the accession's own primary year, not the period a fact actually describes — which broke a foreign-key constraint for any fiscal year whose only data lives as a comparative inside a *later* filing (SHOP has no standalone 10-K for FY2023, only comparative data inside its FY2024 10-K); fixed to derive from `CanonicalFact` instead, the correct source of truth. (2) `raw_facts.concept` was `VARCHAR(128)`, too narrow for real XBRL custom-extension tag names (hit a 140-char CP stock-compensation tag immediately); widened to 256 via migration. All four companies are now ingested and scored against real EDGAR + Tiingo data as a result — which is what made the golden-dataset gaps above visible in the first place.

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

**Workflow note (2026-07-22):** Lawrence is moving to doing most work from mobile/cloud Claude Code sessions going forward, stepping away from the desktop session. This file is the handoff mechanism — read it fully before starting anything, especially the golden-dataset investigation above, which is genuinely mid-flight, not finished.

## What's left

Phase 1 (all 4 epics) is implemented and verified against real data; the frontend has a real design system. **The active task is the golden-dataset investigation above — resume there first, in a session that actually has Docker/Postgres/network access (see the session note above).** After that's closed out, in rough priority order:

1. **Deploy to real cloud infra** — nothing has been pushed to Render/Vercel/a real Supabase project yet; everything so far is local-only (local Docker Postgres, local dev servers).
2. ~~**Not-investment-advice disclaimer**~~ — **done 2026-07-22:** site-wide footer (`frontend/app/layout.tsx`) + a one-line caption on the company page's Verdict section (`frontend/app/company/[ticker]/page.tsx`). Wording/placement resolved as a product-copy call; whether Canada-specific legal review is warranted is still open (PRD Open Question 3).
3. **Phase 2 features** — Value lens, Growth lens, Filing Q&A (LangGraph), Thesis Journal — per the already-committed roadmap in `epics.md`/the PRD.
4. **Epic retrospective** — `bmad-retrospective` hasn't been run yet for Phase 1; there's real material for it (the shares_outstanding bug, the accession_number bug, the parallel-session incident, this golden-dataset investigation).

Or invoke **`bmad-help`** for authoritative routing if priorities shift. The story backlog lives in `_bmad-output/planning-artifacts/epics.md` (4 epics, 26 stories, all marked `done` in `sprint-status.yaml`).

**Local dev environment, for a fresh session picking this up:**
- `docker run -d --name thesistrace-pg -e POSTGRES_PASSWORD=devpass -e POSTGRES_DB=thesistrace -p 5432:5432 postgres:17` (a second `thesistrace_test` database is also needed — `docker exec thesistrace-pg psql -U postgres -c "CREATE DATABASE thesistrace_test;"` — tests use `TEST_DATABASE_URL`, never `DATABASE_URL`, or pytest's table-dropping teardown will wipe your dev data — this bit us once already, see `.env.example`'s comment).
- `cp .env.example .env`, fill in `DATABASE_URL`/`TEST_DATABASE_URL` pointing at the containers above, a real `TIINGO_API_KEY` (needed for Altman), `EDGAR_CONTACT` (quoted, no unescaped parens — breaks `uv run --env-file` parsing otherwise).
- `cd backend && uv run --project backend --env-file ../.env alembic upgrade head` (run from repo root, not `backend/`, if invoking the bare `uv run alembic` form).
- `TEST_DATABASE_URL=... uv run pytest -v` → expect 48 passed, 1 skipped.
- `uv run --env-file ../.env uvicorn app.main:app --reload` (backend, `:8000`) and `cd frontend && npm run dev` (frontend, `:3000`) in separate terminals.
- To populate real company data: `uv run --env-file ../.env python3 -m pipeline.run` from `backend/` (requires a real `TIINGO_API_KEY` for Altman; degrades gracefully to Piotroski/Beneish/Sloan-only without one).

## Everything on disk right now

```text
ThesisTrace/
  HANDOFF.md                                    # this file
  CLAUDE.md                                     # binding git-workflow rule (branch + PR, every session)
  README.md                                     # quickstart, stack, deployment notes
  render.yaml                                   # backend deploy config (not yet actually deployed)
  backend/                                      # FastAPI + batch pipeline — Epics 1-4 implemented
    app/, ingestion/, raw_store/, canonicalization/, validation/, formulas/, scoring/, explanation/, api/, pipeline/
    tests/                                      # 48 passing tests; tests/golden/phase1_golden.yaml is PLACEHOLDER, not real
  frontend/                                     # Next.js — Tailwind design system, all 4 pages
    app/globals.css, app/components/ui/         # design tokens + reusable primitives
  db/migrations/                                # Alembic migrations
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
    epics.md                                    # Phase-1 epics/stories, all marked done
  _bmad-output/implementation-artifacts/
    sprint-status.yaml                          # generated 2026-07-21, all Phase-1 stories done
```
