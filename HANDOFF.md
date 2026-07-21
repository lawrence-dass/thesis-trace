# ThesisTrace — Project Handoff

**Purpose of this file:** a single entry point for picking this project back up from a different device or session (e.g. Claude Code mobile/cloud) with zero prior context. Read this first.

## What ThesisTrace is

An evidence-backed equity intelligence platform for retail investors. Four transparent analytical lenses (Value, Growth, Quality/Health, Integrity) computed deterministically from SEC EDGAR filings — never an LLM-invented score. An LLM layer explains already-computed results and answers filing-grounded questions, but never originates a number or gives investment advice. Full product vision: `_bmad-output/planning-artifacts/prds/prd-ThesisTrace-2026-07-17/prd.md`.

Consolidates two prior concepts (LedgerLens + Fundalens); the original comparison is now in-repo at `_bmad-output/planning-artifacts/ledgerlens-fundalens-consolidation-review.md` (copied 2026-07-20 from its original location outside version control, so cloud/mobile sessions can read it).

## Where things stand (as of 2026-07-19)

| Artifact | Status | Path |
|---|---|---|
| Foundational decisions (D1–D7) | **Locked** | `_bmad-output/planning-artifacts/foundational-decisions.md` |
| PRD | **Final** | `_bmad-output/planning-artifacts/prds/prd-ThesisTrace-2026-07-17/prd.md` (+ `addendum.md` in the same folder) |
| Architecture spine | **Draft — Finalize in progress, paused mid-review** | `_bmad-output/planning-artifacts/architecture/architecture-ThesisTrace-2026-07-19/ARCHITECTURE-SPINE.md` |
| Epics & Stories | **Not started** | — |
| Application code | **Not started** | — |
| Git repo / GitHub | **Not yet initialized** (Lawrence doing this himself) | — |

## Architecture spine — exact resume point

The spine itself (15 ADs: paradigm, data model, ingestion/canonicalization rules, formula versioning, hosting, etc.) is drafted and reads as complete — but the BMad Architecture skill's Finalize sequence was interrupted partway through, deliberately, to switch to this handoff. Do not treat the spine as final yet.

**Done:**
1. Distill — spine written from the coaching session's memlog.
2. Reconcile — checked against the PRD; found and fixed one real issue (AD-11 adopting Tiingo as a market-data source silently conflicted with a locked "no multiple data providers" constraint — resolved by amending `foundational-decisions.md` D7 with an explicit, narrowly-scoped exception, confirmed by Lawrence).

**Not done:**
3. Reviewer Gate — the deterministic lint (`lint_spine.py`) ran clean (0 findings), but the rubric walker and the two configured reviewer lenses (verify-web-researched-decisions, adversarial-two-independent-units-test) were dispatched and then interrupted before finishing. **No review files exist yet.**
4. Triage open items.
5. Polish / renderings (spine-only was chosen as the deliverable — no extra walkthrough artifact needed).
6. External handoffs (none configured).
7. Close — flip frontmatter `status: draft` → `final`.

**To resume:** invoke the `bmad-architecture` skill again (or just ask to continue the architecture finalize) — it will find the existing run under `_bmad-output/planning-artifacts/architecture/architecture-ThesisTrace-2026-07-19/` and should reload `.memlog.md`, whose last entry states this exact resume point.

Full run memory: `_bmad-output/planning-artifacts/architecture/architecture-ThesisTrace-2026-07-19/.memlog.md` (30 entries — every decision made during the architecture coaching session, with reasoning).

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

Two PRD-touching refinements surfaced during architecture work and are recorded but **not yet folded back into `prd.md`** — do this before or during epics/stories work:
- FR-12 (AI explanation) should tighten to "deterministic template first, LLM as constrained rewrite only" (spine AD-7).
- FR-9 (Verdict) should state the actual synthesis rule now defined (spine AD-12) in place of the current placeholder language.
- FR-4/FR-5 (Altman) should note the Tiingo market-data dependency (spine AD-11).

## How Lawrence works (for any AI session picking this up)

This isn't captured anywhere else in the repo — it's local assistant memory on the desktop machine, which a cloud/mobile session won't have access to:

- **Wants research-backed grounding, not assertions.** Before a feature, competitor-differentiation claim, or technical assumption gets locked in, verify it (live data checks, web research, named comparables) rather than reasoning from training data alone. He explicitly invites this ("you can do research if needed") and expects it even when he doesn't ask.
- **Quality over reduced scope.** When a real technical gap surfaces (e.g., Altman's market-data dependency), don't default to the option that cuts scope or defers the hard part just because it's offered as "the pragmatic choice." He's willing to invest more engineering effort to keep a feature fully correct rather than simplify it away. Solve the underlying problem; reserve simplification for when the simpler path is *also* the higher-quality one.
- **Catches gaps himself and expects them taken seriously.** His "wait, did we cover X?" questions (e.g. the missing multi-ticker comparison feature, the Altman data question) are genuine gap-finding, not idle curiosity — verify before answering rather than reassuring from memory.
- **Values honest pushback.** He responded well to direct pushback like "wrapping a trivial LLM call in LangGraph would read as keyword-stuffing to a technical reviewer" — don't just validate every idea.

## What's left before development starts

1. Finish the architecture spine Finalize sequence (resume point above).
2. Fold the three PRD-touching refinements above back into `prd.md` (a `bmad-prd` Update run).
3. Recommended next BMad steps once the spine is final: `bmad-spec` (adopt the spine as a companion spec, keeping AD IDs stable) → `bmad-create-epics-and-stories` → `bmad-create-story` for the first story. Or invoke `bmad-help` for authoritative routing if priorities shift.
4. Git repo + GitHub — Lawrence is initializing this himself; once done, this `HANDOFF.md` should move with the repo (keep it at project root) so it's the first thing a cloud/mobile session sees.

## Everything on disk right now

```text
ThesisTrace/
  HANDOFF.md                                    # this file
  _bmad-output/planning-artifacts/
    foundational-decisions.md                   # D1-D7, locked
    prds/prd-ThesisTrace-2026-07-17/
      prd.md                                    # final
      addendum.md                                # competitor/whitespace research depth
      .memlog.md                                 # full PRD-run decision trail
      review-rubric.md, reconcile-*.md           # PRD review/reconciliation artifacts
    architecture/architecture-ThesisTrace-2026-07-19/
      ARCHITECTURE-SPINE.md                      # draft, Finalize paused (see above)
      .memlog.md                                 # full architecture-run decision trail
      reconcile-prd.md                           # reconciliation findings (AD-11/D7 issue)
      reviews/                                   # empty - reviewer gate not yet run
```
