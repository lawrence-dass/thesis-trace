---
title: ThesisTrace — PRD/Foundational-Decisions Reconciliation
purpose: Input-reconciliation pass (Finalize step 2) comparing prd.md (FR-1–FR-21) and foundational-decisions.md against ARCHITECTURE-SPINE.md
created: '2026-07-20'
sources:
  - '_bmad-output/planning-artifacts/prds/prd-ThesisTrace-2026-07-17/prd.md'
  - '_bmad-output/planning-artifacts/foundational-decisions.md'
  - '_bmad-output/planning-artifacts/architecture/architecture-ThesisTrace-2026-07-19/ARCHITECTURE-SPINE.md'
---

# Reconciliation Findings

## 1. Headline gap — AD-11 (Tiingo) silently breaches a locked standing constraint

`foundational-decisions.md`, "Standing constraints carried forward from the consolidation review" (unlabeled but immediately preceding D6; the doc header marks the whole file **"Locked (revisit only via explicit correct-course)"**):

> **Stack:** Next.js/TypeScript + FastAPI/Python + Supabase Postgres (+ pgvector for first RAG). **No MongoDB, Qdrant, DynamoDB, or multiple data providers before an end-to-end product exists.**

`ARCHITECTURE-SPINE.md` AD-11 (`[ADOPTED]`, binds FR-4/FR-5):

> Altman Z-Score's market value of equity = period-end closing price (**Tiingo** free tier) × EDGAR `dei:EntityCommonStockSharesOutstanding` at FYE.

This is a second data provider (EDGAR + Tiingo) adopted **in Phase 1**, i.e. explicitly before an end-to-end product exists — the precise condition the standing constraint forbids. The PRD itself is aware such a principle exists and treats it as load-bearing: Non-Goals §5 rejects broad news/sentiment aggregation partly because it "would require new paid data providers (conflicting with the single-provider-first principle in D7)." (Note: the PRD's own citation of "D7" for this principle is itself slightly off — the actual "no multiple data providers" line lives in the unlabeled Standing Constraints block, not in D7, which is about charting/LangGraph. That's a pre-existing PRD citation slip, not something the spine needs to fix, but worth flagging to the PM alongside this finding.)

**Why this matters technically:** AD-11's own reasoning is sound — EDGAR alone can't give a correct as-of-FYE market value of equity (`EntityPublicFloat` is wrong-dated, book value is the wrong substitute per FR-4's own consequence text) — so *some* second source is arguably unavoidable for Altman in Phase 1. That's a legitimate architectural discovery. But it directly contradicts a decision explicitly marked locked, and unlike AD-7 (which gets an explicit "flagged as a PRD-touching refinement pending PM confirmation" note), **AD-11 carries no such flag** — it's marked `[ADOPTED]` as if it were a routine, uncontested choice. This is exactly the kind of change the input-reconciliation pass exists to catch: it should be surfaced to Lawrence for an explicit correct-course/PRD-update decision (e.g., amend the standing constraint to "no multiple *paid* data providers" or "no additional providers beyond what Phase 1 deterministic scoring strictly requires"), not silently adopted.

**Recommendation:** Add an explicit flag to AD-11 mirroring AD-7's treatment, and log a foundational-decisions.md correct-course item.

## 2. AD-12 (Verdict per-model juxtaposition) — contrast case, no gap

AD-12 specifies *how* FR-9's "transparent, stated-rule synthesis" is realized (side-by-side per-model threshold classification, never blended into one number). Checked against the PRD: FR-9's consequences only say the Verdict must be "a transparent, stated-rule synthesis... never an LLM-invented number" — it does not commit to a specific presentation shape, so juxtaposition is a legitimate architecture-level choice filling a gap the PRD deliberately left open, not a narrowing of an existing commitment. Nothing in Non-Goals or foundational-decisions.md conflicts with it either. **Unlike AD-11, this one does not need a PRD-update flag** — the spine's silence here is appropriate, not a gap.

## 3. AD-7 (deterministic-first explanation) — handled correctly

AD-7 explicitly states: "Tightens FR-12 beyond the PRD's 'cited narrative' language; flagged as a PRD-touching refinement pending PM confirmation." This is exactly the right treatment and is good news, not a gap — worth confirming to Lawrence that this one FR/AD pair is already correctly surfaced. (Arguably AD-7 is the *smaller* deviation of the two — FR-12's glossary entry for "Explanation" already says "Never originates a number" — yet it's the one that got flagged, while AD-11's larger deviation from a locked standing constraint did not. That asymmetry is itself worth noting to the PM.)

## 4. Open Questions — resolved vs. still open

- **OQ2 (amended/restated filings policy) — resolved.** AD-6 (append-only versioned `score_runs`, amendment triggers new run + supersedes prior) explicitly states "Resolves PRD Open Question 2." Correctly handled, good news.
- **OQ1 (golden-dataset sourcing), OQ3 (disclaimer wording), OQ5–OQ9** — correctly left open; none require an architecture-spine-level answer (they're data-sourcing, legal/copy, or Phase 2/3 product decisions). No gap.
- **OQ4 (cost ceiling, resolved 2026-07-17 at ~$25/month) — partially unaddressed.** The Stack table marks Vercel "free/hobby tier," Supabase "free-tier," and Tiingo "free tier API" explicitly, but the Render row just says "Web Service + Cron Job" with no tier/cost annotation, and AD-13's own rationale only argues Render avoids *split-platform* overhead versus Fly.io/Railway — it never states the resulting monthly cost or confirms it sits under the $25 ceiling. Since Render's free web-service tier and cron-job billing are not the same thing (cron jobs are typically billed separately, even if cheap), the spine should either state the expected Render cost explicitly or note the assumption. Minor gap, not a contradiction.

## 5. Non-Goals check — no violations found

Walked all Non-Goals in §5 against the spine:
- No LLM-generated canonical scores — consistent (AD-1, AD-7, AD-8 all reinforce deterministic-only computation).
- No brokerage/trade execution — absent from spine, no violation.
- No full market coverage, no native mobile, no off-the-shelf charting, no sector heatmap/dashboard — none appear in the spine; no violation.
- No user accounts/passwords beyond Phase-3 email capture — AD-10's "operator-only, shared-secret header" admin path is explicitly *not* end-user auth and is correctly scoped as ops-only, consistent with foundational-decisions D4. No accidental auth creep.
- No IFRS support, no SEDAR+/TSX-only ingestion — both correctly absent from scope; SEDAR+ is explicitly named in the spine's own Deferred section as an "explicit PRD Non-Goal, no phase scheduled." Good — self-consistent.
- No formal a11y/performance/uptime NFR targets for v1 — spine's Deployment & environments section explicitly defers "NFR rigor (monitoring, alerting, rollback)... to Phase 4," matching the PRD's own Non-Goals framing exactly.

## 6. Minor observation (not elevated to a gap)

FR-3/FR-4/FR-6 each require every sub-signal/ratio/index to be "individually computed and stored, not just the aggregate" (9 Piotroski signals, 5 Altman ratios, 8 Beneish indices). The structural seed's `SCORE_RESULTS` entity isn't detailed enough in the spine to confirm it stores per-signal rows rather than just an aggregate score per `score_run`. Given the spine explicitly treats comparably granular items (e.g., "exact accounting-identity validation rule set") as implementation detail rather than spine-level invariant, this is likely intentional and fine to leave — flagging only so it isn't lost before the data-model/epic pass.

---

# Summary of PRD-touching changes: surfaced vs. silently absorbed

| Spine decision | Touches PRD/foundational-decisions? | Flagged in spine? |
|---|---|---|
| AD-7 (deterministic-first explanation, narrows FR-12) | Yes | **Yes** — explicit "PRD-touching... pending PM confirmation" note |
| AD-11 (Tiingo as second data provider for FR-4/5) | Yes — contradicts locked "no multiple data providers before an end-to-end product exists" | **No** — marked `[ADOPTED]` with no PRD/correct-course flag |
| AD-12 (Verdict per-model juxtaposition for FR-9) | No — fills a gap the PRD left open, doesn't override a stated commitment | Correctly not flagged (none needed) |
