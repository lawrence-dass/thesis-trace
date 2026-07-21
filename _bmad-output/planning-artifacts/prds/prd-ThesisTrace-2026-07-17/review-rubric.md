# PRD Quality Review — ThesisTrace (prd-ThesisTrace-2026-07-17)

## Overall verdict

This is a substantively strong PRD: the thesis is real and drives feature sequencing, trade-offs are named rather than smoothed over, and scope honesty is unusually disciplined (assumptions, notes-for-PM, and non-goals all roundtrip cleanly). The main risk is mechanical, not conceptual — a Functional-Requirement renumbering pass (documented in `.memlog.md` as fixing the missing Altman FR) left five stale cross-references pointing at the wrong FR numbers, which matters because this PRD explicitly exists so "downstream architecture, UX, and epic/story work can cite [FRs] directly" (§0). Phase 2/3 FRs are also thinner than the rubric wants for done-ness, though that's substantially by design given their "directional" labeling.

## Decision-readiness — strong

Trade-offs are named with what was given up, not just what was chosen. The clearest example is §4.12's Notes (line 276): "Email-only identity capture and email-only delivery channel were chosen deliberately over full auth or in-app-only notifications, to keep the deviation from `foundational-decisions.md` D4's no-auth stance as small as possible while still exercising real queue/worker/notification-delivery engineering." That's a trade-off stated with its cost, not hedged.

The nine Open Questions (§8) are genuinely open — none are rhetorical-with-the-answer-already-given. E.g., OQ2 ("when a 10-K/A supersedes a 10-K a score was already computed from, does the system recompute automatically, flag for manual review, or something else?") names real unresolved branches rather than a foregone conclusion. `[NOTE FOR PM]` callouts (lines 276, 288, 290, 309) land on real tensions — e.g. line 309 flags that Thesis Journal, "the feature most directly tied to the product's name and core differentiation," is deferred to Phase 2/3, which is the kind of uncomfortable admission the rubric is looking for, not a safe checkpoint.

No findings — this dimension doesn't need fixing.

## Substance over theater — strong

Only two personas (Daniel; an unnamed "technical reviewer"), both doing real work — well under the four-persona red flag. The differentiation claim for the Thesis Journal is unusually well-calibrated rather than asserted: addendum.md §A2 checks it against Simply Wall St Narratives, usethesis.com, PageCrawl.io, and FilingRadar, and lands on "Position as 'a more rigorous version of an emerging pattern,' not 'first of its kind'" — the opposite of innovation theater. The Vision statement (§1) names the specific four models (Piotroski, Altman, Beneish, Sloan) and the specific "keep checking that evidence against reality" hook — it couldn't swap into a generic fintech PRD unchanged. No NFR boilerplate anywhere (grepped for "scalable/secure/reliable/seamless/robust" — zero hits), so there's no NFR theater to flag, though see Done-ness clarity for the flip side of that.

No findings — this dimension doesn't need fixing.

## Strategic coherence — strong

The thesis ("deterministic forensic scores computed from raw XBRL with provenance are achievable and trustworthy," per `foundational-decisions.md` D5, correctly cross-referenced rather than restated) drives the Phase 1/2 split: Integrity + Quality/Health ship first specifically because they're "fully mechanical," Value/Growth wait because they're "judgment-heavy." MVP Scope (§6) follows from this, not from ease. Success Metrics validate the thesis rather than measuring activity: SM-1 is correctness against a golden dataset, not usage volume. The counter-metrics are sharp and specific — SM-C1 explicitly blocks expanding the Company Universe as "a vanity metric before SM-1 (correctness) is solid," and SM-C2 explicitly refuses to let Notifications become an engagement lever. This is a stronger counter-metric pairing than most PRDs manage.

No findings — this dimension doesn't need fixing.

### Findings

- **medium** Three Phase 2 FRs carry zero testable consequences (§4.8–§4.10) — See Done-ness clarity below for detail; noted here because it's the one place strategic coherence and done-ness interact (a thesis-driven roadmap still needs each future FR anchored, even thinly).

## Done-ness clarity — adequate

Phase 1 FRs are genuinely strong on this dimension. FR-3/FR-4/FR-6 each enumerate their sub-signals as individually stored (not just the aggregate), version their formulas explicitly, and specify the "insufficient data" fallback rather than a guess. FR-7's threshold language is concrete: "Flagged as a high-accrual warning when it crosses the published threshold, with the threshold value stated explicitly (not just 'high'/'low')" (line 158). This is exactly the unforgiving specificity the rubric wants.

The gap is Phase 2's FR-15, FR-16, and FR-17 (§4.8–§4.10, lines 226–239). Each is a single sentence with no "Consequences (testable)" block at all — contrast with FR-18 through FR-21, which are also marked "directional, detailed at architecture stage" but still carry 2–3 testable bullets each. An engineer (or architect) reading FR-16 ("The system computes valuation metrics per company with stated assumptions and sensitivity ranges") has no way to know what "done" looks like even at a directional level — no mention of which metrics, what a "sensitivity range" must show, or what happens when inputs are missing (the FR-3-style graceful-degradation pattern isn't carried forward here even as a placeholder).

### Findings

- **medium** FR-15/16/17 have no testable consequences at all (lines 226–239) — Every other FR in the document, including the similarly "directional" FR-18–FR-21, has at least 2 testable bullets; these three have none, breaking the pattern the rest of the PRD establishes. *Fix:* add one placeholder consequence per FR (even something as light as "graceful degradation follows the FR-3 'insufficient data' pattern") so downstream readers aren't left with a bare section header.
- **low** No NFR/performance/security section anywhere in the PRD — Given the stated hobby/solo stakes (per `.memlog.md`: "Stakes: hobby/solo scale... but full rigor on Features/FR sections") this is likely an intentional and reasonable scope call, but it's never stated as one — there's no Non-Goal or Open Question marking "no performance/uptime targets for v1." *Fix:* one line in §5 or §8 making the omission explicit rather than silent.

## Scope honesty — strong (one gap)

The Non-Goals section (§5) does real work — eleven bullets, several with `[NON-GOAL for MVP]` and `[NOTE FOR PM]` tags at genuinely deferred decisions (e.g., line 288's news/8-K non-goal explicitly names what was considered and why it was rejected rather than just asserting it's out). The Assumptions Index (§9) roundtrips cleanly: all three inline `[ASSUMPTION]` tags (FR-13's 4-company cap at line 214, SM-2's 3-month window at line 320, mobile web-only at line 287) are indexed, and the index has no orphan entries. Open-items density (9 Open Questions + 3 Assumptions + 4 Notes-for-PM = 16) is proportionate for a hobby/solo-stakes PRD, not a red flag.

One real omission survives from the source consolidation review and was never given the explicit-non-goal or open-question treatment the PRD otherwise uses consistently: the original LedgerLens/Fundalens review's Phase 2 headline items "historical trends" and "one or two high-value financial visualizations" (per `reconcile-consolidation-review.md` Gap 5) do not appear anywhere in `prd.md` — not as an FR, not in Non-Goals, not in Open Questions. This is inconsistent with how the PRD otherwise handles dropped source material: the sibling items "sector heatmap" and "draggable dashboards" from the same source list *were* carried forward into Non-Goals (line 289: "No sector heatmap, no draggable/resizable dashboard UI... same treatment as full market coverage above"), and the lens sub-metrics gap was carried forward as Open Question 9. Historical-trend visualization has no such landing spot, despite Growth Lens (FR-17) being the natural place for it.

### Findings

- **medium** "Historical trends" / "financial visualizations" from the source consolidation review have no trace in the PRD (checked via grep — no hits for "historical trend" or "visualiz" outside the TradingView-exclusion context) — Every other item from the same source "features to defer/keep" lists was either carried into an FR, a Non-Goal, or an Open Question; this pair was silently dropped instead. *Fix:* add a bullet to Non-Goals or fold into FR-17's future scope, even directionally.

## Downstream usability — adequate

The Glossary (§3) is thorough (16 terms) and used consistently — "Provenance," "Canonical Fact," "Company Universe," and "Verdict" all appear capitalized and identically-defined everywhere checked. FR IDs are contiguous and unique (FR-1 through FR-21, no gaps or duplicates verified by direct grep). SM IDs (SM-1–4, SM-C1–2) and UJ IDs (UJ-1–5) are likewise clean.

However, several inline FR cross-references are stale — leftovers from the FR renumbering documented in `.memlog.md` ("Renumbered FR-4 through FR-20 to FR-5 through FR-21... updated all cross-references (MVP Scope, Success Metrics, Assumptions Index)" — that pass evidently missed some inline "Consequences" bullets and one Open Question):

- Line 164 (FR-8's consequences): "Same provenance-linking pattern as FR-4" — FR-4 (Altman computation) never establishes a provenance-linking pattern; that's FR-5 ("Each value links to its Provenance record"). Should read FR-5.
- Line 220 (FR-14's consequences): "consistent with FR-8's phase honesty" — FR-8 is Integrity sub-signal display/accounting-identity validation, not phase-honesty; the "live vs. pending lenses" concept is established in FR-9 (line 176). Should read FR-9.
- Line 328 (SM-C2): "Notifications (FR-18–FR-20)" — Notifications & Deep Research Requests is §4.12, containing FR-19–FR-21; FR-18 is Thesis Journal (§4.11), a different feature. Should read FR-19–FR-21 (§6.2, line 310, already gets this right, showing the two aren't consistent with each other).
- Line 338 (Open Question 7): "Notifications (FR-18–FR-20)" — same error as above.
- Line 337 (Open Question 6): "browser-local storage (FR-17)" in the context of Thesis Journal persistence — FR-17 is Growth trajectory metrics (§4.10), unrelated; Thesis Journal is FR-18. Should read FR-18.

Separately, UJ-2's protagonist (line 49) is not a fixed named individual: "A technically-minded visitor (could be a fellow engineer, could be Daniel himself feeling skeptical)." Every other UJ names Daniel specifically; UJ-2 hedges between two different personas with different needs (a first-time external reviewer vs. Daniel re-checking his own work), which downstream UX work would have to resolve on its own.

### Findings

- **high** Five stale FR cross-references from an incomplete renumbering pass (lines 164, 220, 328, 337, 338) — Because this PRD's stated purpose (§0) is that FR IDs are "globally-numbered, stable... so downstream architecture, UX, and epic/story work can cite them directly," wrong ID citations are exactly the failure mode this design was meant to prevent; a downstream workflow doing ID-based extraction would pull the wrong FR's content in at least two of these five spots (FR-8 vs FR-5, FR-17 vs FR-18). *Fix:* a single find-and-verify pass over every "FR-N" citation in the document against its actual referent.
- **low** UJ-2 has a floating, unnamed protagonist rather than a fixed one (line 49) — Inconsistent with UJ-1/3/4/5's consistent use of "Daniel," and leaves open whether the technical-reviewer journey is a distinct persona or Daniel-in-a-different-mode. *Fix:* pick one framing (a named second persona, or explicitly "Daniel, in skeptical/technical mode") and use it consistently.

## Shape fit — strong

This is a hobby/solo-scale, single-primary-user product with a stated ~20%-weighted secondary technical-reviewer audience (D2), and the PRD's rigor is calibrated to that correctly: full FR rigor (versioned formulas, provenance, testable consequences) where real financial scores are computed (Phase 1), lighter directional treatment for Phase 2/3 features not yet architected. UJs are load-bearing here — this is a real (if narrow) consumer-facing product, not an internal tool, so named-protagonist UJs are the right shape choice, and the PRD uses them for exactly that reason. No over-formalization detected (no NFR padding, no accessibility program at hobby scale — line 290 explicitly defers this with a `[NOTE FOR PM]` rather than silently omitting it or over-building it).

No findings — this dimension doesn't need fixing.

## Mechanical notes

- **ID continuity:** FR-1 through FR-21 verified contiguous and unique; UJ-1–5, SM-1–4/SM-C1–2 likewise clean.
- **Broken cross-refs:** See Downstream usability above — 5 instances of stale FR-number citations from an incomplete renumbering pass (lines 164, 220, 328, 337, 338). This is the single mechanical issue worth fixing before this PRD is cited by downstream architecture/UX/story work.
- **Assumptions Index roundtrip:** Clean. All 3 inline `[ASSUMPTION]` tags (lines 214, 287, 320) are indexed in §9, and §9 has no entries without an inline counterpart.
- **Glossary drift:** None found — spot-checked "Provenance," "Canonical Fact," "Verdict," "Company Universe," "Comparison," "Deep Research Request" for consistent casing/usage across FRs; all consistent.
- **Cross-document references:** All `foundational-decisions.md` D1–D7 citations verified to exist and match the cited content (confirmed against `/Users/lawrence/Desktop/ThesisTrace/_bmad-output/planning-artifacts/foundational-decisions.md`). The `.memlog.md` and `reconcile-*.md` files in this same directory confirm the Altman-FR gap, the D1 "working title" contradiction, and several dropped Non-Goals were already identified and fixed in this draft — those are resolved and not re-flagged here.
