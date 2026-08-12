# Handover — 2026-08-12 | Claude Opus 5

## Mode
Between epics — **Epic 6 is COMPLETE (7 of 7)** and merged. Nothing in flight.

## Focus
- **Task**: Epic 6 — reverse DCF. Done and closed.
- **Branch**: `main` at `80f3ec5` (PR #64 squash-merged 2026-08-12). No open PRs, no
  branches but `main` locally or remotely.
- **Suite**: CI green on `main`. With a database configured the backend suite is
  **310 passed / 1 skipped**; DB tests run in CI (postgres:17 service).

## Resume Point
Epic 6 closed. `epic-7: backlog`, `epic-6-retrospective: optional`.

**FOUR THINGS ARE OPEN AND NONE BLOCKS EPIC 7 — but two of them are decisions that
were meant to be made BEFORE Epic 6 closed, and it closed without them:**

1. **The sensitivity grid is computed on read, not stored.** Story 6.4's AC says
   stored "so a read cannot trigger computation (AD-1)". Measured at 2.9 ms per
   35-cell grid, ~20 ms for a 7-filer compare page. Either persist it in its own
   story or amend 6.4's AC to say computed-on-read with the cost recorded. Do not
   leave the AC and the code disagreeing. **Storing it needs an idempotency key or
   the nightly cron accumulates a row a night — the anti-pattern that bit
   `run_validation`.** See `story_6_5_open_deviations` in sprint-status.
2. **The overview N+1 is real and measured**: `get_company_overview` issues 484
   queries for OTEX (20 fiscal years), 343 for CP, 100 for SHOP. Story 6.5 adds +2
   to +3, flat — it inherits the N+1, it does not cause it. Recommended: land a
   query-count test against a long-history issuer NOW (cheap, pins 484 so it cannot
   silently become 900), defer the batching to Track P.
3. **The market-price date backfill is still open** and the fix is INERT until it
   runs. Ingestion now writes real observation dates, so no new bad rows accumulate,
   but `uq_market_prices_key` is `(issuer_cik, price_date, source)` and the
   mislabelled weekend row is LATER than the true Friday one, so the lookup still
   prefers it. No numerical impact (same close). Needs its own change with a guard
   asserting no stored observation lands on a non-trading day.
4. **There is no frontend test runner at all** — `devDependencies` has eslint and
   tsc but no test framework, and CI's frontend job is lint + build only. Story 6.6
   therefore ships `formatRate`, `joinList` and the band-plot `pos()` as pure,
   trivially testable, untested functions. Adding a runner is a new dependency plus
   a CI step; it was judged out of scope for 6.6 rather than overlooked.

## Uncommitted Files
None.

## What Happened This Session
- **Story 6.5 merged** (PR #62, `e23b5ae`) and the handover updated (PR #63).
- **Story 6.6 — reverse DCF on the company overview** (frontend). Custom band
  visualisation, no charting library. Verified in a browser against the live
  database, which found three defects that lint, tsc and the build all passed clean.
- **/code-review on PR #64 returned five findings, all confirmed against the live
  API before being accepted.** The worst: the `insufficient_data` card discarded
  `historical_revenue_cagr`, which the backend computes independently of whether the
  DCF resolves — so the one card with no implied figure was hiding the only half of
  the comparison it had (Suncor 7.7%, SHOP 27.3%).
- **Story 6.7 — golden coverage over the reverse DCF.** All seven filers carry an
  entry. Expected rates solved by a reimplementation written from the spec text that
  imports nothing from `backend/valuation`, `backend/scoring` or `backend/formulas`.
- **PR #64 merged as `80f3ec5`**, closing Epic 6.

## Decisions Made
- **THE GOLDEN FIXTURES ARE TRIMMED SUBSETS, and this was invisible until something
  tried to USE them for a new capability.** CP's carried 23 us-gaap tags and neither
  a capex nor a cash-and-equivalents tag, so every filer resolved to
  `insufficient_data` — the golden entries would have looked complete while
  asserting nothing. The mappings were fine (`concepts_v8`); the fixtures were the
  gap. Rebuilt from the dev store's own `raw_facts` joined to `filings` (already-
  ingested EDGAR data, keyed to accession numbers) rather than re-fetching. **Assume
  any future capability hits this same wall.**
- **Adding source tags CAN change canonicalization**, so it was checked explicitly:
  the suite went 309 → 310 with no other assertion moving. CP's reverse-DCF
  `total_debt` is the same 22,494,000,000 its debt-share entry already pinned.
- **Golden values are computed independently ON PURPOSE.** A value produced by
  calling the code under test asserts only that the code agrees with itself. Cost
  accepted and recorded in the test: a spec change must be mirrored by hand.
- **Suncor has NO capex tag in any year under any variant** — confirmed twice (live
  2026-08-07, and again against the dev store while extending fixtures, where every
  other filer's tag was found). Its `insufficient_data` is real. Its debt and cash
  operands ARE present, which is what separates "the model does not apply" from
  "the data is missing".

## Context Needed
- **`test_health_db_503_when_unconfigured` fails locally and is NOT a regression.**
  It does `monkeypatch.delenv("DATABASE_URL")`, but a gitignored `.env` at the repo
  root is read directly by pydantic `Settings` — settings-from-file sit below the env
  layer, so unsetting the variable removes only one of two sources. CI has no `.env`.
  The fix, if ever wanted, is the pattern at `backend/tests/test_health.py:29`:
  `Settings(_env_file=None)`.
- **DB tests need `TEST_DATABASE_URL` EXPORTED** — conftest reads `os.environ` only,
  not `.env`, so they skip silently in a plain local run (219 passed instead of 310).
  `DATABASE_URL` is deliberately not a fallback: `db_session` runs `drop_all` on
  whatever it resolves.
- **The repo moved.** It now lives at `/Users/lawrence/Documents/projects/ThesisTrace`,
  not on the Desktop. The Desktop path is gone; a macOS TCC permission failure on the
  Desktop folder is what prompted the move. The orphaned Claude project directory
  `~/.claude/projects/-Users-lawrence-Desktop-ThesisTrace` can be deleted.
- **Squash merge is this repo's convention** — the `(#N)` subject suffix with a single
  parent. Note this means Epic 6 closed inside `80f3ec5`, whose subject names only
  Story 6.6; 6.7 and the review fixes are in its body.
- Bucket coverage by `period_end` against the issuer's own FYE, never the payload's
  `fy` field. OTEX's FYE is June 30.
- Golden entries must be extended in the SAME change as any capability (SM-1).

## Next Action
Decide items 1 and 2 above, then either run the Epic 6 retrospective (optional) or
start Epic 7 planning. Nothing blocks Epic 7.

## References
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `story_6_7_golden_coverage`,
  `story_6_6_browser_verification`, `story_6_5_open_deviations`,
  `market_price_dates_labelled_as_fiscal_year_end`
- `backend/tests/test_golden_dataset.py` — the independent solver and why it imports nothing
- `backend/formulas/specs/reverse_dcf_v1.yaml` — the five assumptions, the solver, AD-16 cases
- `frontend/app/components/ReverseDcf.tsx` — the band plot
- project-context.md: `.claude/context/project-context.md`

---
*Generated 2026-08-12 after PR #64 closed Epic 6.*
