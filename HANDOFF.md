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
| Golden-dataset verification (SM-1 / PRD OQ1) | **CLOSED (2026-07-29) — all four companies (SHOP, QSR, CP, OTEX) are real, hand-verified golden entries.** See the sections below. | `backend/tests/golden/phase1_golden.yaml` |
| Verdict Beneish visibility bug | **Fixed 2026-07-29** — Verdict was hiding real historical Beneish scores (QSR 2017-2023, OTEX 2011-2019) behind an unrelated insufficient_data FY2025 run. See the section below. | `backend/api/repository.py` |
| Verdict "why is this missing" indication | **Added 2026-07-29** — when a model's aggregate is genuinely insufficient_data (CP/SHOP's Beneish), the Verdict card now names which specific sub-signals are missing in plain language (e.g. "Missing: Gross Margin, SG&A Ratio") instead of a bare dash with no explanation. | `frontend/app/company/[ticker]/page.tsx`, `frontend/app/compare/page.tsx` |
| Git repo / GitHub | **Initialized** (`lawrence-dass/thesis-trace`), Phase 1 + design system merged to `main` via PRs #1–#6, live-data bug fixes via PR #7/#8, canonicalization/FX + Beneish-coverage fixes via PR #9/#10, golden-dataset entries via PR #11/#12/#14/#16, a concurrent session's GitHub Actions CI + enterprise UX redesign via PR #15/#17, Verdict fixes via PR #18 (all merged). Branch-per-session + PR workflow is now binding — see `CLAUDE.md`. | — |

## 🟢 Verdict now explains WHY a score is missing, not just a bare dash (2026-07-29)

Follow-up to the fix below: Lawrence asked why CP and SHOP's Beneish still show "—" after the Verdict-selection fix, and — after the explanation — asked for the UI to indicate this directly rather than requiring an explanation each time. Both are genuine, permanent data limitations (CP has no COGS/SGA tags at all; SHOP's debt reclassifies between current/noncurrent in a way that would produce a misleading leverage signal if force-mapped), not something to fix further.

Added a plain-language "why" explanation instead of a bare dash, confirmed with Lawrence via `AskUserQuestion` (chose the specific option over a generic "Insufficient data"-only badge):

- **Backend**: `VerdictItem` gained a `missing_signals: list[str]` field — populated with the specific sub-signal keys that are `insufficient_data` for that model's chosen Verdict year (only when the aggregate itself is `None`; empty otherwise). Computed for free from data `get_company_overview` was already fetching (each `LensScoreOut`'s own `signals` list), no new query needed.
- **Frontend**: added a `SIGNAL_LABEL` map (plain-language names for Beneish/Altman/Sloan's sub-signals, e.g. `gmi` → "Gross Margin") mirroring the existing `MODEL_CAPTION` pattern. The company page's Verdict card now shows an "Insufficient data" badge (reusing the existing `pending` badge style) plus a "Missing: X, Y" caption when an aggregate is null; the Compare page's more compact table shows the same list as a hover tooltip instead, to avoid cluttering the table.
- Two regression tests added (`test_verdict_prefers_latest_year_with_a_value` extended to cover this; new `test_verdict_falls_back_to_latest_when_never_valid` assertion), verified via git-stash.
- **Verified live** against the actual running dev servers (not just unit tests) — confirmed the real rendered HTML shows "Missing: Gross Margin, SG&A Ratio" for CP and "Missing: Leverage" for SHOP, on both the company page and the Compare page's tooltip.

## Verdict was hiding real Beneish scores; CP's ppe_net mapping gap fixed (2026-07-29)

Lawrence reported the live frontend showing Beneish M-Score as "—" for all 4 companies on their Verdict cards and asked to debug before fixing. Investigation found this was NOT a uniform data gap — it split into two very different situations:

**The real, high-impact bug**: `api/repository.py`'s `get_company_overview` picked each model's *latest existing ScoreRun*, regardless of whether that run actually resolved a value. Since `score_beneish` runs for every scoreable year (creating a row even when `insufficient_data`), the Verdict was always showing whichever year happened to be newest — hiding real, valid Beneish scores that already sit in the database: **QSR has 7 valid years (2017-2023)**, **OTEX has 9 (2011-2019)**, both invisible behind an unrelated FY2025 `insufficient_data` run. Fixed to prefer the latest year WITH a value, falling back to the latest run's `insufficient_data` state only when no year ever resolves (confirmed via `AskUserQuestion` — Lawrence chose this over keeping uniform-latest-year or a "last computed: FYxxxx" annotation). Two new regression tests added and verified via git-stash (fail on old code, pass on new): `test_verdict_prefers_latest_year_with_a_value` and `test_verdict_falls_back_to_latest_when_never_valid`.

**One genuine, smaller mapping bug found along the way**: CP switched to a combined "PP&E + finance-lease right-of-use-asset" tag (`PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization`) starting with its FY2021 10-K — the old single-tag mapping never picked this up, silently starving Beneish's AQI/DEPI indices for CP's FY2021/2024/2025. Added as a priority-1 fallback; verified live CP's `ppe_net` now resolves for all years 2014-2025. This does **not** flip CP's Beneish visibility, though — COGS/SGA are still permanently absent for CP (a railroad reporting functional expense categories instead), so all 8 Beneish indices can never simultaneously resolve for CP regardless.

**One nuanced finding deliberately left alone**: SHOP does carry debt (convertible notes, found via `ConvertibleDebtNoncurrent`/`ConvertibleDebtCurrent` tags — the earlier "SHOP has no long-term debt" conclusion was incomplete). But EDGAR reclassifies the same debt between Current and Noncurrent as it nears maturity, so a naive fallback would make Piotroski's `leverage_decreasing` and Beneish's LVGI show leverage swinging to zero when the debt hasn't actually been repaid — just relabeled. Lawrence chose (via `AskUserQuestion`) to leave this as `insufficient_data` rather than risk a misleading signal; summing current+noncurrent as a redefined "total debt" was the alternative, not taken.

Full suite: 53 passed, 1 skipped (up from 51 — the two new Verdict-selection regression tests).

## SHOP FY2024 hand-verified — fourth and final company, SM-1/OQ1 CLOSED (2026-07-29)

Same process one last time, for SHOP FY2024 — closing out the golden-dataset investigation that began 2026-07-22.

| Model | Hand-computed | Pipeline-stored | Match |
|---|---|---|---|
| Piotroski F-Score | 5/9 (all 9 signals verified individually) | 5 | ✓ |
| Sloan accruals ratio | 0.031955 → "Low accruals (higher quality)" | 0.031955 | ✓ |
| Altman Z-Score | 36.292041 (all 5 components verified individually) → "Safe" | 36.292041 | ✓ |
| Beneish M-Score | N/A — SHOP genuinely has no `long_term_debt` XBRL tag at all (confirmed live: a real zero-debt company) — LVGI, and so the aggregate, is correctly `insufficient_data` | `insufficient_data` | ✓ (correctly absent) |

**Found the existing SHOP fixture was entirely synthetic**, not real EDGAR data: `shop_company_facts.json` has fabricated accession numbers (`0001594805-24-000010`/`-25-000010` — neither exists in real EDGAR) and tags SHOP doesn't actually use (`Liabilities`, `CostOfRevenue`, `LongTermDebtNoncurrent`, `SellingGeneralAndAdministrativeExpense`, `AccountsReceivableNetCurrent`). This matches the original 2026-07-22 warning that SHOP's golden values were "characterization values computed from a synthetic fixture, not hand-verified" — the fixture itself was equally unreal, not just the expected values.

That fixture is used by 9 other test files (`test_ingestion.py`, `test_canonicalization.py`, `test_pipeline.py`, etc.) for structural/mechanics testing unrelated to real-world numeric accuracy — replacing it wholesale would have broken all of their hardcoded characterization assertions for no benefit here. Instead, added a separate, real-data fixture (`shop_real_company_facts.json`, real EDGAR payload from SHOP's actual FY2024 10-K, accession `0001594805-25-000012` — SHOP has no standalone FY2023 10-K at all, its FY2023 figures exist only as that filing's comparative column) used exclusively by the golden-dataset entry. The original synthetic fixture is untouched and still serves the other 9 test files.

Full suite: 51 passed, 1 skipped. **This closes PRD Open Question 1 / SM-1**: every company in the Phase-1 universe now has a real, independently hand-verified golden entry, not a placeholder or synthetic characterization value.

## OTEX FY2019 hand-verified — third pilot company (2026-07-26)

Same process again, for OTEX FY2019 — the most instructive pilot of the three, since it surfaced several genuine restatement conflicts in the real EDGAR data (not bugs — the "as-originally-filed wins" rule, AD-3, is exactly what resolves these correctly):

| Model | Hand-computed | Pipeline-stored | Match |
|---|---|---|---|
| Piotroski F-Score | 7/9 (all 9 signals verified individually) | 7 | ✓ |
| Sloan accruals ratio | -0.075263 → "Low accruals (higher quality)" | -0.075263 | ✓ |
| Altman Z-Score | 2.699877 (all 5 components verified individually) → "Grey" | 2.699877 | ✓ |
| Beneish M-Score | -2.884422 (all 8 indices verified individually) → "No manipulation flag" | -2.884422 | ✓ |

Notable findings while independently pulling OTEX's real EDGAR data (all correctly handled by the existing pipeline, not new bugs):

- **OTEX's `total_liabilities` is derived, not tagged** — OTEX never tags `us-gaap:Liabilities` at all (same situation as SHOP); the `total_assets - stockholders_equity` fallback from PR #9 correctly covers it too, not just SHOP as originally documented.
- **Three genuine restatement conflicts**, each correctly resolved by preferring the originally-filed figure over a later comparative that differs slightly: FY2018's `ebit` (505,403,000 originally filed vs. 506,693,000 restated in later filings), `cash_from_operations` (709,885,000 vs. 708,081,000), and `sga` (205,313,000 vs. 205,227,000).
- **Different fallback tags win in different years for the same concept** — FY2018's `cogs` resolves via `CostOfRevenue` (priority 0) while FY2019's resolves via `CostOfGoodsAndServicesSold` (priority 1, since OTEX's FY2019 10-K doesn't tag `CostOfRevenue` at all) — both correctly reachable through the existing priority-ordered fallback chain.

**Also fixed a real bug in the test harness found while wiring OTEX up**: `_run_pipeline` hardcoded `date(fiscal_year, 12, 31)` for the FYE market-price lookup date — correct for SHOP/QSR/CP (all December fiscal-year-ends) but wrong for OTEX, whose fiscal year ends June 30. Would have silently produced `insufficient_data` for Altman instead of matching the hand-verified value. Fixed by adding an explicit `fye_date` field to each golden entry instead of assuming Dec 31.

Added `backend/tests/fixtures/otex_company_facts.json` (real EDGAR payload, OTEX's FY2018/FY2019 10-Ks, 20 concepts) and flipped OTEX's `phase1_golden.yaml` entry to `status: active`. Full suite: 51 passed, 1 skipped — and for the first time, zero "pending coverage" warning, since all four companies in the Phase-1 universe now have a golden-dataset fixture.

**What's left for full SM-1/OQ1 closure**: only SHOP's own entry, still the original placeholder from before this investigation began. Worth the same hand-verification pass — `status: active` on that entry currently only certifies "has a fixture," not "hand-verified against real filings," which remains a latent trap in the data model (the two meanings share one field) worth fixing if this pattern continues.

## CP FY2023 hand-verified — second real golden-dataset entry (2026-07-25)

Same pilot process as QSR below, applied to CP FY2023 — the harder case, since CP reports entirely in CAD and needs the FX conversion. Independently pulled CP's real EDGAR company-facts JSON and cross-checked every canonical input the pipeline had stored; every one matched exactly (including confirming CP's own FY2022 10-K doesn't tag `PropertyPlantAndEquipmentNet` at all — its FY2022 comparative genuinely comes only from the FY2023 10-K, which the pipeline already handled correctly).

| Model | Hand-computed | Pipeline-stored | Match |
|---|---|---|---|
| Piotroski F-Score | 6/9 (all 9 signals verified individually) | 6 | ✓ |
| Sloan accruals ratio | -0.002738 → "Low accruals (higher quality)" | -0.002738 | ✓ |
| Altman Z-Score | 2.145200 (all 5 components verified individually, incl. the CAD/FX conversion) → "Grey" | 2.145200 | ✓ |
| Beneish M-Score | N/A — CP genuinely has no COGS/SGA tags (a railroad reporting functional expense categories instead, confirmed live, not a bug) | `insufficient_data` | ✓ (correctly absent) |

Independently confirmed the FX rate too: Bank of Canada's own published USD/CAD rate for 2023-12-29 (the last trading day before the Sunday 2023-12-31 FYE) is 1.3226, exactly matching what's stored in `fx_rates`.

- Added `backend/tests/fixtures/cp_company_facts.json` (real EDGAR payload, CP's FY2022/FY2023 10-Ks, 15 concepts).
- Extended `test_golden_dataset.py`'s `_run_pipeline` to support an `fx_rate` field per company (needed for any non-USD reporting filer's Altman) and to handle a golden entry whose Beneish `m_score` is genuinely `null` (asserts `insufficient_data`, not skipped).
- **Also fixed a second, unrelated gap in the same test found while extending it**: the `band` field under `altman` in `phase1_golden.yaml` existed for every company (SHOP, QSR) but nothing had ever actually asserted it — only `z_score` was checked. Added the missing assertion.

Full suite: 51 passed, 1 skipped (unchanged — fixes to an existing test file, no new test files).

**Next step:** only OTEX remains for full SM-1/OQ1 closure, plus a hand-verification pass on SHOP's still-placeholder entry.

## QSR FY2023 hand-verified — first real golden-dataset entry (2026-07-24)

With PR #9 and #10 merged, picked QSR FY2023 as the hand-verification pilot. Independently pulled QSR's real EDGAR company-facts JSON (bypassing the pipeline/DB entirely) and cross-checked every canonical input the pipeline had stored — every single one matched exactly. Then hand-computed all four models from those confirmed-correct figures:

| Model | Hand-computed | Pipeline-stored | Match |
|---|---|---|---|
| Piotroski F-Score | 6/9 (all 9 signals verified individually) | 6 | ✓ |
| Sloan accruals ratio | 0.017123 → "Low accruals (higher quality)" | 0.017123 | ✓ |
| Beneish M-Score | -2.219847 (all 8 indices verified individually) → "No manipulation flag" | -2.219847 | ✓ |
| Altman Z-Score | 1.471660 (all 5 components verified individually) → "Distress" | 1.471660 | ✓ |

Nothing was off by even a rounding digit. Formalized this into the actual golden-dataset infrastructure, mirroring SHOP's existing fixture pattern (a committed, trimmed real EDGAR JSON, not a live-network test):

- Added `backend/tests/fixtures/qsr_company_facts.json` — the real EDGAR payload for QSR's FY2022 and FY2023 10-Ks (accessions 0001618756-23-000013 and -24-000020), trimmed to only the 17 concepts the mappings actually consume.
- QSR's `phase1_golden.yaml` entry flipped to `status: active` with the hand-verified numbers above (fye_close 78.13, the real Tiingo/EDGAR-confirmed 2023-12-31 close).
- **Found and fixed a real bug in the test harness itself while wiring this up**: `test_golden_dataset.py`'s Piotroski/Sloan queries never filtered by company — invisible with only one active company (SHOP) in `phase1_golden.yaml`, but adding QSR as a second active company immediately produced a nonsensical F-score of 13 (SHOP's 7 passing signals + QSR's 6 leaking together in the same session query). Fixed by scoping both queries to the company's own `ScoreRun.issuer_cik`.

Full suite: 51 passed, 1 skipped (unchanged count — one test fixed, no test added, since the golden-dataset test itself now exercises two companies instead of one).

**Next step:** CP and OTEX still need the same treatment (real fixture + hand-verification + `status: active`) to fully close PRD Open Question 1 / SM-1. SHOP's entry is also still the OLD placeholder — worth a hand-verification pass too, not just assumed correct because it's marked `active` (that flag currently only means "has a fixture," not "hand-verified" — a naming trap for whoever picks this up next).

## Round 2 of the golden-dataset investigation — 10 more bugs fixed, PR #9 + #10 merged (2026-07-23)

Resumed the investigation below and, before touching the actual hand-verification work, found and fixed ten more real correctness bugs across two PRs (full detail in each PR's description and commit message — this is a summary):

1. **SHOP's total_liabilities never resolved** (SHOP never tags `us-gaap:Liabilities`) — added `stockholders_equity` mapping + a derived `total_liabilities = total_assets - stockholders_equity` fallback (accounting identity, verified exact against real SHOP figures).
2. **Beneish never computed for any company** — `cogs`/`sga`/`long_term_debt` never resolved. Added verified priority-ordered fallback tags (this closes the item the 2026-07-22 note below flagged as the next concrete step).
3. **CP's revenue/net_income missing 2014-2021** — added `Revenues`/`ProfitLoss` fallback mappings.
4. **CP's Altman X4 silently mixed USD (Tiingo price) and CAD (CP's own reporting currency)** — added a Bank of Canada Valet API integration (new `fx_rates` table, `backend/ingestion/fx.py`, `backend/raw_store/fx_rates.py`) to convert market value of equity into CAD before computing X4. Lawrence explicitly chose this over marking Altman insufficient_data or sourcing a CAD price feed.
5. **`ParsedFiling.fiscal_year_end` corrupted by dei cover-page dates** winning a naive first-or-max selection over the true us-gaap fiscal-year-end — this was silently misdating every FX-rate and Tiingo-price lookup keyed off it.
6. **10-K/A amendments silently overrode the original 10-K's more reliable fiscal_year_end** in per-fiscal-year filing lookups — added a shared `_primary_filing_per_year` helper (mirrors AD-3's as-originally-filed principle).
7. **Canonicalization grouped raw facts purely by `period_end.year`**, causing two distinct real collisions: a 10-K's quarterly "selected financial data" footnote sharing the true annual figure's `period_end` (CP revenue/ebit, 2014-2021), and an accounting-standard-adoption "opening balance as of Jan 1" snapshot landing in the same calendar year as the true Dec-31 closing balance (QSR FY2018/2019 balance sheet). Fixed by filtering candidates to full-year-duration facts whose `period_end` matches the issuer's own recognized fiscal-year-end day (with tolerance, since OTEX's FYE occasionally shifts a few days off June 30).
8. **QSR's FY2016 cash_from_operations** used a `NetCashProvidedByUsedInOperatingActivitiesContinuingOperations` tag variant never in the mapping table — added the fallback. (Items 1-8: PR #9.)
9. **QSR's Beneish never computed for ANY fiscal year** (not just 2024-2025 as item 2 above assumed) — QSR tags receivables as `AccountsNotesAndLoansReceivableNetCurrent` and depreciation as plain `Depreciation`/`DepreciationAndAmortization`, neither previously mapped. Added fallbacks; QSR's Beneish now resolves 2017-2023.
10. **SHOP's Beneish never computed at all** — SHOP tags receivables as `AccountsAndOtherReceivablesNetCurrent`, also unmapped. Added the fallback. (Items 9-10: PR #10.) SHOP's Beneish still doesn't fully resolve, though — it has no `long_term_debt` XBRL tag at all (genuinely debt-free, not a mapping gap) and its earliest 10-K's balance sheet doesn't reach back far enough for a full year-over-year pair; both left as `insufficient_data` rather than guessed.

Every fix has a regression test verified (via git-stash) to fail on the pre-fix code and pass on the fix, or (items 9-10, following the same precedent as item 2) live pipeline verification. Full suite: 51 passed, 1 skipped (up from 48). Verified against real EDGAR data via a clean-slate database rebuild + full live pipeline re-run across all 4 companies, not just fixtures or reasoning.

**Left correctly flagged, not "fixed":** OTEX's `shares_outstanding` FY2008 has a genuine 1000x scale inconsistency between two of OTEX's own filed comparatives (50,780 vs 50,780,000 — a real filer data-quality issue in EDGAR itself). OTEX also drops its single "total depreciation and amortization" tag after FY2019 in favor of several component tags with no verified combined total. Per AD-3's never-guess rule, both stay `needs_review`/`insufficient_data` rather than picking a value by heuristic.

**Next step:** merge PR #9 (Lawrence's call, not done automatically), then proceed to the actual hand-verification work described in the original investigation section below — the concept-mapping/computation groundwork should now be solid enough to do that without it being invalidated by yet another mapping gap.

## Golden-dataset verification — original investigation (started 2026-07-22)

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
4. ~~**Epic retrospective**~~ — **done 2026-07-22:** `_bmad-output/implementation-artifacts/epic-4-retro-2026-07-22.md` (run as one combined Phase 1 retro, Epics 1-4, at Lawrence's request). Key finding: real bugs (shares_outstanding, accession_number, CIK wiring, and a newly-found `bandTone()` gap that made every Beneish badge render gray since PR #6) were consistently only caught by live-data re-verification, never by the green test suite — 5 action items recorded in `sprint-status.yaml`.
5. **Score-teaching UI** — done 2026-07-22, see below: per-model range/zone gauges + plain-language captions on the company page's Verdict cards, so a visitor sees not just the number but what it means and which direction is favorable. Shipped for the company page only; the Compare page was deliberately left for a later pass.

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
