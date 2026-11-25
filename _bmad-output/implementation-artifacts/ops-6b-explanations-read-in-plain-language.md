# Ops 6b: Explanations read in plain language, without an LLM

Status: review
Date: 2026-11-24
Scope: a figure rendered to a user, so the live-data definition of done applies

## Why

Every per-year card on a company page shows the deterministic explanation
sentence, and it read like a debug line. AAPL FY2026:

> Altman Z-Score for FY2026 is 12.700871 — classified Safe. Signals met:
> x1_working_capital, x2_retained_earnings, x3_ebit, …

> Piotroski F-Score for FY2026 is 9.0 — classified Strong. Signals met:
> accruals, asset_turnover_increasing, cfo_positive, …

Ops 3 rounded headline scores ("12.70", "9"), but this sentence is built on the
backend and still printed the stored six decimals right below them. Signals
appeared under their internal keys.

The LLM "polish" path (retired from reads in Ops 6a) was meant to fix this.
Lawrence chose (2026-11-24) to fix it deterministically instead: no spend, and no
chance of an LLM changing a number. Write-path polishing is parked
(`explanation_llm_polish_parked`) and revisited only if this text still reads poorly.

## Acceptance criteria

1. A score in the sentence uses the same display rule as the headline (Ops 3):
   two decimals, Piotroski a whole number, decimal ROUND_HALF_EVEN, no negative
   zero, and decimals added until the number clears any band boundary the exact
   value does not sit on. Band edges come from the formula spec.
2. The Python rule and `scoreFormat.ts` agree on every test vector in
   `scoreFormat.test.ts`.
3. Signals appear under plain-language names. Every signal key in the four
   formula specs has one, so a new signal fails a test instead of falling back
   to its key.
4. The backend's labels and the frontend's `SIGNAL_LABEL` are identical, and a
   test fails if they drift. `SIGNAL_LABEL` gains the nine Piotroski keys.
5. Nothing else in the sentence changes: band label, caveat text, the
   insufficient-data wording, citations.
6. Rendered in a browser on filers that exercise each path: a boundary guard
   (OTEX FY2013 Altman 2.98734; CCJ FY2018 Beneish -1.78136), a caveat (CP
   Altman), an insufficient aggregate, and an out-of-scope model.

## Tasks

- [x] `backend/explanation/score_format.py`: `format_score` (AC 1)
- [x] `test_score_format.py`: the `scoreFormat.test.ts` vectors, plus OTEX FY2013
      and CCJ FY2018 read from the real specs (AC 2)
- [x] `backend/explanation/signal_labels.py` (AC 3)
- [x] Spec-coverage test and frontend-agreement test (AC 3, 4). Mutation check:
      changing one frontend label fails the agreement test.
- [x] `SIGNAL_LABEL` gains the Piotroski keys (AC 4)
- [x] `template.py` uses both; `test_explanation_template.py` updated from "6.0"
      to the whole-number Piotroski display, with cross-year negatives kept (AC 5)
- [x] `make test` 715 passed; lint clean; frontend 121 tests, tsc, eslint clean
- [x] Rendered against the dev store: AAPL FY2026 (all four models), OTEX FY2013
      (headline and sentence both 2.987), no console errors. API checked across
      all 13 filers: CCJ FY2018 -1.781, CP caveat, AAPL FY2013/14 insufficient
      Beneish; zero internal keys and zero 4+-decimal scores outside guard cases.
      **No filer has an out-of-scope model today**, so that path has its unit
      test only.
- [x] Recorded `explanation_llm_polish_parked`, plus two deferred findings:
      `explanation_components_read_as_signals_met`, `breakdown_rows_show_internal_keys`
- [x] `make api` / `make web` take `API_PORT` / `WEB_PORT` (another session held
      :8001 and :3001); defaults unchanged
- [x] Codex round (MERGE AFTER FIXES). Finding 1 fixed: the label check regex-parsed
      TypeScript and passed after real additions, removals and renames. The map is
      now `frontend/app/lib/signalLabels.json`, imported by BOTH pages (the compare
      page held a third, private copy), and compared as parsed JSON. The formatter
      cases moved to a shared `scoreFormat.vectors.json` that both suites run.
      Mutation-checked: an added key fails the label test; a changed expected
      value fails both suites. Findings 2 and 3 deferred as
      `score_display_has_two_formatters` (neither reachable on the normal path).
- [ ] PR; after merge, **Manual Deploy on Render** (the text is built per request)
